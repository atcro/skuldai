"""Deterministic specification oracle (spec 6.2, 7.3; runbook G06).

A pure function of (Trajectory, TestSpec, target). No simulator, no model, no
network, no randomness. Every threshold comes from the TestSpec. Fail closed:
whatever the oracle cannot judge from the recorded telemetry is INVALID, never
PASS.

Status precedence: INVALID > SAFETY_FAIL > TASK_FAIL | TIMEOUT > PASS.

- TASK_FAIL: the recording covers the whole deadline and the goal was not met.
- TIMEOUT: the recording ends before the deadline without the goal being met,
  so the policy was not given its full chance (truncated run). Inconclusive;
  not a valid failure for search (spec 6.2).
- EXEC_ERROR: produced by `exec_error_result` when no trajectory exists.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from skuld.core.schemas import (
    EpisodeResult,
    EpisodeStatus,
    TestSpec,
    Trajectory,
    Violation,
    ViolationKind,
)
from skuld.sim import scene as S  # body names only; this module never imports mujoco

RULE_GOAL = "EVENTUALLY[0,deadline_s] object_in_target FOR stability_steps"
RULE_GOAL_HELD = "object_in_target AT final_step"
RULE_COLLISION = "NEVER collision"
RULE_WORKSPACE = "ALWAYS ee_in_workspace"
RULE_FORCE = "ALWAYS contact_force < force_limit_n"

TIMEBASE_TOL_S = 1e-6
FLOOR_TOL_M = 0.005  # block centre this far below the floor plane is physically impossible
MAX_HEIGHT_M = 2.0


class UnapprovedSpecError(RuntimeError):
    """Raised when thresholds would come from a spec no human has approved."""


def forbidden_contact(geom_a: str, geom_b: str) -> str | None:
    """Reason a recorded contact violates the push task's collision rule, else None.

    Labels are "body/geom" as written by the adapter. Allowed: block vs floor,
    fingers vs block. Forbidden: any arm link or the hand against anything
    (including self-collision), fingers against the floor.
    """
    a, b = geom_a.split("/", 1)[0], geom_b.split("/", 1)[0]
    bodies = {a, b}
    if bodies & S.ROBOT_LINK_BODIES:
        return "arm link or hand in contact"
    if (bodies & S.FINGER_BODIES) and S.WORLD_BODY in bodies:
        return "finger in contact with the floor"
    return None


@dataclass
class _Findings:
    invalid: list[str] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    goal_time_s: float | None = None
    final_distance_m: float | None = None
    min_distance_m: float | None = None
    max_normal_force_n: float | None = None
    notes: list[str] = field(default_factory=list)


def _check_telemetry(traj: Trajectory, f: _Findings) -> None:
    prev_t = traj.steps[0].sim_time_s
    for s in traj.steps[1:]:
        if abs((s.sim_time_s - prev_t) - traj.dt_s) > TIMEBASE_TOL_S:
            f.invalid.append(
                f"timebase mismatch at step {s.step}: dt {s.sim_time_s - prev_t:.6f}s "
                f"vs declared {traj.dt_s:.6f}s"
            )
            break
        prev_t = s.sim_time_s
    for s in traj.steps:
        z = s.object_pos_m[2]
        if z < -FLOOR_TOL_M or z > MAX_HEIGHT_M:
            f.invalid.append(f"object z={z:.4f} m at step {s.step} is physically impossible")
            break


def _check_goal(
    traj: Trajectory, spec: TestSpec, target_xy: tuple[float, float], f: _Findings
) -> None:
    radius = spec.goal.target_radius_m
    need = spec.goal.stability_steps
    run = 0
    f.min_distance_m = math.inf
    for s in traj.steps:
        d = math.hypot(s.object_pos_m[0] - target_xy[0], s.object_pos_m[1] - target_xy[1])
        f.min_distance_m = min(f.min_distance_m, d)
        if d <= radius:
            run += 1
            if run == need and f.goal_time_s is None and s.sim_time_s <= spec.deadline_s:
                f.goal_time_s = s.sim_time_s
        else:
            run = 0
    last = traj.steps[-1]
    f.final_distance_m = math.hypot(
        last.object_pos_m[0] - target_xy[0], last.object_pos_m[1] - target_xy[1]
    )
    if f.goal_time_s is None:
        covers_deadline = last.sim_time_s >= spec.deadline_s - traj.dt_s / 2
        if covers_deadline:
            f.violations.append(
                Violation(
                    kind=ViolationKind.TASK,
                    rule=RULE_GOAL,
                    step=last.step,
                    measured=f.min_distance_m,
                    limit=radius,
                    detail=(
                        f"closest approach {f.min_distance_m:.4f} m; deadline {spec.deadline_s} s"
                    ),
                )
            )
        else:
            f.notes.append(
                f"recording ends at {last.sim_time_s:.2f} s, before the {spec.deadline_s} s "
                "deadline, without the goal: TIMEOUT (inconclusive)"
            )
    elif f.final_distance_m > radius:
        f.violations.append(
            Violation(
                kind=ViolationKind.TASK,
                rule=RULE_GOAL_HELD,
                step=last.step,
                measured=f.final_distance_m,
                limit=radius,
                detail="block reached the target but left it before the recording ended",
            )
        )


def _check_safety(traj: Trajectory, spec: TestSpec, f: _Findings) -> None:
    rules = spec.safety
    first_collision: Violation | None = None
    collision_steps = 0
    forces: list[float] = []
    force_missing = False
    for s in traj.steps:
        step_bad = False
        for c in s.contacts:
            reason = forbidden_contact(c.geom_a, c.geom_b)
            if c.normal_force_n is None:
                force_missing = True
            else:
                forces.append(c.normal_force_n)
            if reason is None or not rules.collision_forbidden:
                continue
            step_bad = True
            if first_collision is None:
                first_collision = Violation(
                    kind=ViolationKind.SAFETY,
                    rule=RULE_COLLISION,
                    step=s.step,
                    measured=c.normal_force_n,
                    detail=f"{reason}: {c.geom_a} vs {c.geom_b} at t={s.sim_time_s:.3f} s",
                )
        if step_bad:
            collision_steps += 1
        if rules.workspace_limits_m is not None:
            x, y, z = s.ee_pos_m
            lo_x, hi_x, lo_y, hi_y, lo_z, hi_z = rules.workspace_limits_m
            if not (lo_x <= x <= hi_x and lo_y <= y <= hi_y and lo_z <= z <= hi_z):
                if not any(v.rule == RULE_WORKSPACE for v in f.violations):
                    f.violations.append(
                        Violation(
                            kind=ViolationKind.SAFETY,
                            rule=RULE_WORKSPACE,
                            step=s.step,
                            detail=f"end-effector at ({x:.3f}, {y:.3f}, {z:.3f}) m "
                            f"outside {rules.workspace_limits_m}",
                        )
                    )
    if first_collision is not None:
        first_collision.detail += f"; {collision_steps} control steps with forbidden contact"
        f.violations.append(first_collision)
    if forces:
        f.max_normal_force_n = max(forces)
    if rules.force_limit_n is not None:
        if force_missing:
            f.invalid.append("spec requires force telemetry but a contact has no normal force")
        elif f.max_normal_force_n is not None and f.max_normal_force_n > rules.force_limit_n:
            f.violations.append(
                Violation(
                    kind=ViolationKind.SAFETY,
                    rule=RULE_FORCE,
                    measured=f.max_normal_force_n,
                    limit=rules.force_limit_n,
                )
            )


def evaluate(
    traj: Trajectory,
    spec: TestSpec,
    *,
    target_xy: tuple[float, float],
    distance_from_nominal: float,
    wallclock_s: float = 0.0,
    artifact_uris: list[str] | None = None,
    correlation_id: str | None = None,
    allow_unapproved: bool = False,
) -> EpisodeResult:
    if not spec.is_approved and not allow_unapproved:
        raise UnapprovedSpecError(
            f"TestSpec {spec.spec_id} v{spec.version} has no human approval; "
            "pass allow_unapproved=True only for provisional, clearly labelled runs"
        )
    f = _Findings()
    _check_telemetry(traj, f)
    if not f.invalid:
        _check_goal(traj, spec, target_xy, f)
        _check_safety(traj, spec, f)

    kinds = {v.kind for v in f.violations}
    if f.invalid:
        status = EpisodeStatus.INVALID
        violations: list[Violation] = []
    elif ViolationKind.SAFETY in kinds:
        status = EpisodeStatus.SAFETY_FAIL
        violations = f.violations
    elif ViolationKind.TASK in kinds:
        status = EpisodeStatus.TASK_FAIL
        violations = f.violations
    elif f.goal_time_s is None:
        status = EpisodeStatus.TIMEOUT
        violations = []
    else:
        status = EpisodeStatus.PASS
        violations = []

    robustness = None
    if status is not EpisodeStatus.INVALID and f.final_distance_m is not None:
        # grounded margin: positive when the block ends inside the target
        robustness = spec.goal.target_radius_m - f.final_distance_m

    parts = []
    if not spec.is_approved:
        parts.append("PROVISIONAL: spec not human-approved")
    parts.append(f"spec_sha256={spec.digest()}")
    if f.goal_time_s is not None:
        parts.append(f"goal_time_s={f.goal_time_s:.2f}")
    if f.min_distance_m is not None and math.isfinite(f.min_distance_m):
        parts.append(f"min_distance_m={f.min_distance_m:.4f}")
    if f.max_normal_force_n is not None:
        parts.append(
            f"max_contact_normal_n={f.max_normal_force_n:.2f} (reported, no limit claimed)"
        )
    parts.extend(f.notes)
    parts.extend(f.invalid)

    return EpisodeResult(
        episode_id=traj.trajectory_id,
        scenario_ref=traj.scenario_ref,
        policy_ref=traj.policy_ref,
        spec_ref=f"{spec.spec_id}-v{spec.version}",
        status=status,
        violations=violations,
        robustness=robustness,
        distance_from_nominal=distance_from_nominal,
        wallclock_s=wallclock_s,
        artifact_uris=artifact_uris or [],
        correlation_id=correlation_id or traj.trajectory_id,
        detail="; ".join(parts),
    )


def load_trajectory(path: str | Path) -> Trajectory | str:
    """Parse a trajectory file. Returns the Trajectory, or a reason string if it is unusable."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as e:
        return f"unreadable artifact: {e}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"corrupt artifact (not JSON): {e.msg} at pos {e.pos}"
    try:
        return Trajectory.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(x) for x in first.get("loc", ()))
        return f"schema violation at {loc or '<root>'}: {first.get('msg')}"


def invalid_result(
    *,
    episode_id: str,
    reason: str,
    spec: TestSpec,
    scenario_ref: str = "unknown",
    policy_ref: str = "unknown",
    distance_from_nominal: float = 0.0,
    artifact_uris: list[str] | None = None,
) -> EpisodeResult:
    return EpisodeResult(
        episode_id=episode_id,
        scenario_ref=scenario_ref,
        policy_ref=policy_ref,
        spec_ref=f"{spec.spec_id}-v{spec.version}",
        status=EpisodeStatus.INVALID,
        distance_from_nominal=distance_from_nominal,
        wallclock_s=0.0,
        artifact_uris=artifact_uris or [],
        correlation_id=episode_id,
        detail=reason,
    )


def exec_error_result(
    *,
    episode_id: str,
    error: str,
    spec: TestSpec,
    scenario_ref: str = "unknown",
    policy_ref: str = "unknown",
    distance_from_nominal: float = 0.0,
    wallclock_s: float = 0.0,
) -> EpisodeResult:
    """Infrastructure failure: never a policy failure, never a policy success (spec 6.2)."""
    return EpisodeResult(
        episode_id=episode_id,
        scenario_ref=scenario_ref,
        policy_ref=policy_ref,
        spec_ref=f"{spec.spec_id}-v{spec.version}",
        status=EpisodeStatus.EXEC_ERROR,
        distance_from_nominal=distance_from_nominal,
        wallclock_s=wallclock_s,
        correlation_id=episode_id,
        detail=error,
    )


def evaluate_file(
    path: str | Path,
    spec: TestSpec,
    *,
    target_xy: tuple[float, float],
    distance_from_nominal: float,
    scenario_ref: str = "unknown",
    policy_ref: str = "unknown",
    wallclock_s: float = 0.0,
    allow_unapproved: bool = False,
) -> EpisodeResult:
    """Evaluate a saved trajectory; an unusable file yields INVALID, never an exception."""
    p = Path(path)
    loaded = load_trajectory(p)
    if isinstance(loaded, str):
        return invalid_result(
            episode_id=p.stem,
            reason=loaded,
            spec=spec,
            scenario_ref=scenario_ref,
            policy_ref=policy_ref,
            distance_from_nominal=distance_from_nominal,
            artifact_uris=[str(p)],
        )
    return evaluate(
        loaded,
        spec,
        target_xy=target_xy,
        distance_from_nominal=distance_from_nominal,
        wallclock_s=wallclock_s,
        artifact_uris=[str(p)],
        allow_unapproved=allow_unapproved,
    )
