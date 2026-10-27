"""G06: the deterministic oracle, on synthetic trajectories (no simulator needed).

Kept lean on purpose (spec 12.2): one trajectory builder, one parametrised
status table, and a few checks that cannot be expressed as a table row.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skuld.core.schemas import Contact, EpisodeStatus, Trajectory, TrajectoryStep, ViolationKind
from skuld.oracle import evaluate as O
from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M, approve

SPEC = approve(PUSH_SPEC_V1, "test-fixture", datetime(2026, 10, 26, tzinfo=UTC))
DT = 1.0 / 50.0
START = (0.45, -0.15)
SCENE_SHA = "0" * 64


def make_traj(
    *,
    n_steps: int,
    reach_step: int | None,
    leave_step: int | None = None,
    contacts: dict[int, list[Contact]] | None = None,
    ee_z: float = 0.03,
    block_z: float = 0.02,
    dt_recorded: float = DT,
    dt_declared: float = DT,
    final_fraction: float = 1.0,
) -> Trajectory:
    """Block slides from START to the target by `reach_step` (None: never moves)."""
    steps = []
    for i in range(n_steps):
        if reach_step is None:
            a = 0.0
        else:
            a = min(1.0, i / reach_step) * final_fraction
        if leave_step is not None and i >= leave_step:
            a = 2.0  # overshoots far past the target
        x = START[0] + a * (TARGET_XY_M[0] - START[0])
        y = START[1] + a * (TARGET_XY_M[1] - START[1])
        steps.append(
            TrajectoryStep(
                step=i,
                sim_time_s=(i + 1) * dt_recorded,
                qpos=[0.0] * 16,
                qvel=[0.0] * 15,
                object_pos_m=(x, y, block_z),
                ee_pos_m=(x, y - 0.03, ee_z),
                action=[0.0] * 8,
                contacts=(contacts or {}).get(i, []),
            )
        )
    return Trajectory(
        trajectory_id="traj-synthetic",
        scenario_ref="synthetic",
        policy_ref="synthetic-policy",
        sim_name="synthetic",
        sim_version="0",
        scene_sha256=SCENE_SHA,
        dt_s=dt_declared,
        steps=steps,
    )


FLOOR_FINGER = Contact(geom_a="world/floor", geom_b="left_finger/68", normal_force_n=12.0)
FINGER_BLOCK = Contact(geom_a="left_finger/68", geom_b="block/block_geom", normal_force_n=3.0)
LINK_BLOCK = Contact(geom_a="link5/40", geom_b="block/block_geom", normal_force_n=1.0)
FULL = int(round(SPEC.deadline_s / DT))  # 750 steps covers the whole deadline


@pytest.mark.parametrize(
    ("name", "kwargs", "status", "rule"),
    [
        ("success", dict(n_steps=400, reach_step=150), EpisodeStatus.PASS, None),
        (
            "never_moves_full",
            dict(n_steps=FULL, reach_step=None),
            EpisodeStatus.TASK_FAIL,
            O.RULE_GOAL,
        ),
        ("never_moves_truncated", dict(n_steps=300, reach_step=None), EpisodeStatus.TIMEOUT, None),
        (
            "reaches_then_leaves",
            dict(n_steps=400, reach_step=150, leave_step=300),
            EpisodeStatus.TASK_FAIL,
            O.RULE_GOAL_HELD,
        ),
        (
            "too_late",
            dict(n_steps=FULL + 500, reach_step=FULL + 400),
            EpisodeStatus.TASK_FAIL,
            O.RULE_GOAL,
        ),
        (
            "finger_on_floor_but_goal_reached",
            dict(n_steps=400, reach_step=150, contacts={10: [FLOOR_FINGER], 11: [FLOOR_FINGER]}),
            EpisodeStatus.SAFETY_FAIL,
            O.RULE_COLLISION,
        ),
        (
            "arm_link_touches_block",
            dict(n_steps=400, reach_step=150, contacts={200: [LINK_BLOCK]}),
            EpisodeStatus.SAFETY_FAIL,
            O.RULE_COLLISION,
        ),
        (
            "finger_on_block_is_allowed",
            dict(n_steps=400, reach_step=150, contacts={i: [FINGER_BLOCK] for i in range(50, 160)}),
            EpisodeStatus.PASS,
            None,
        ),
        (
            "ee_below_floor_is_workspace_breach",
            dict(n_steps=400, reach_step=150, ee_z=-0.05),
            EpisodeStatus.SAFETY_FAIL,
            O.RULE_WORKSPACE,
        ),
        (
            "block_below_floor",
            dict(n_steps=400, reach_step=150, block_z=-0.02),
            EpisodeStatus.INVALID,
            None,
        ),
        (
            "timebase_mismatch",
            dict(n_steps=400, reach_step=150, dt_recorded=0.05),
            EpisodeStatus.INVALID,
            None,
        ),
    ],
)
def test_status_table(name: str, kwargs: dict, status: EpisodeStatus, rule: str | None) -> None:
    r = O.evaluate(make_traj(**kwargs), SPEC, target_xy=TARGET_XY_M, distance_from_nominal=0.0)
    assert r.status is status, (name, r.detail, [v.model_dump() for v in r.violations])
    if rule is None:
        assert not r.violations
    else:
        assert any(v.rule == rule for v in r.violations), [v.rule for v in r.violations]
    if status is EpisodeStatus.SAFETY_FAIL:
        # safety dominates and the first offending step is reported
        v = next(v for v in r.violations if v.kind is ViolationKind.SAFETY)
        assert v.step is not None
    if status is EpisodeStatus.PASS:
        assert r.robustness is not None and r.robustness > 0
        assert "goal_time_s=" in r.detail
    if status is EpisodeStatus.INVALID:
        assert r.robustness is None and "PROVISIONAL" not in r.detail
    assert r.status.is_valid_failure == (
        status in (EpisodeStatus.TASK_FAIL, EpisodeStatus.SAFETY_FAIL)
    )


def test_thresholds_come_only_from_the_spec() -> None:
    # covers the whole deadline and stops 3 cm short, so the verdict hinges on the radius
    traj = make_traj(n_steps=FULL, reach_step=150, final_fraction=0.9)
    tight = SPEC.model_copy(update={"goal": SPEC.goal.model_copy(update={"target_radius_m": 0.02})})
    short = SPEC.model_copy(update={"deadline_s": 1.0})
    assert (
        O.evaluate(traj, SPEC, target_xy=TARGET_XY_M, distance_from_nominal=0.0).status
        is EpisodeStatus.PASS
    )
    assert (
        O.evaluate(traj, tight, target_xy=TARGET_XY_M, distance_from_nominal=0.0).status
        is EpisodeStatus.TASK_FAIL
    )
    assert (
        O.evaluate(traj, short, target_xy=TARGET_XY_M, distance_from_nominal=0.0).status
        is EpisodeStatus.TASK_FAIL
    )
    # a spec nobody approved is refused unless the run is explicitly provisional
    with pytest.raises(O.UnapprovedSpecError):
        O.evaluate(traj, PUSH_SPEC_V1, target_xy=TARGET_XY_M, distance_from_nominal=0.0)
    r = O.evaluate(
        traj, PUSH_SPEC_V1, target_xy=TARGET_XY_M, distance_from_nominal=0.0, allow_unapproved=True
    )
    assert r.status is EpisodeStatus.PASS and r.detail.startswith("PROVISIONAL")
    assert f"spec_sha256={PUSH_SPEC_V1.digest()}" in r.detail


def test_force_limit_needs_telemetry_and_is_enforced() -> None:
    with_force = SPEC.model_copy(
        update={
            "safety": SPEC.safety.model_copy(
                update={"force_telemetry_available": True, "force_limit_n": 10.0}
            )
        }
    )
    hard = make_traj(
        n_steps=400,
        reach_step=150,
        contacts={100: [FINGER_BLOCK.model_copy(update={"normal_force_n": 11.0})]},
    )
    r = O.evaluate(hard, with_force, target_xy=TARGET_XY_M, distance_from_nominal=0.0)
    assert r.status is EpisodeStatus.SAFETY_FAIL and r.violations[0].rule == O.RULE_FORCE
    missing = make_traj(
        n_steps=400,
        reach_step=150,
        contacts={100: [FINGER_BLOCK.model_copy(update={"normal_force_n": None})]},
    )
    r = O.evaluate(missing, with_force, target_xy=TARGET_XY_M, distance_from_nominal=0.0)
    assert r.status is EpisodeStatus.INVALID and "force telemetry" in r.detail


def test_unusable_artifacts_and_exec_errors_fail_closed(tmp_path: Path) -> None:
    good = make_traj(n_steps=400, reach_step=150)
    ok = tmp_path / "ok.json"
    ok.write_text(good.model_dump_json())
    assert (
        O.evaluate_file(ok, SPEC, target_xy=TARGET_XY_M, distance_from_nominal=0.0).status
        is EpisodeStatus.PASS
    )
    truncated = tmp_path / "truncated.json"
    truncated.write_text(good.model_dump_json()[:5000])
    nan = tmp_path / "nan.json"
    d = json.loads(good.model_dump_json())
    d["steps"][7]["object_pos_m"][0] = math.nan
    nan.write_text(json.dumps(d))
    extra = tmp_path / "extra.json"
    d = json.loads(good.model_dump_json())
    d["verdict"] = "PASS"  # a field nobody defined, e.g. injected by a model
    extra.write_text(json.dumps(d))
    for p, needle in (
        (truncated, "corrupt"),
        (nan, "schema violation"),
        (extra, "schema violation"),
    ):
        r = O.evaluate_file(p, SPEC, target_xy=TARGET_XY_M, distance_from_nominal=0.0)
        assert r.status is EpisodeStatus.INVALID, p.name
        assert needle in r.detail
        assert not r.status.is_valid_failure
    missing = O.evaluate_file(
        tmp_path / "nope.json", SPEC, target_xy=TARGET_XY_M, distance_from_nominal=0.0
    )
    assert missing.status is EpisodeStatus.INVALID and "unreadable" in missing.detail
    e = O.exec_error_result(episode_id="ep-x", error="container OOM", spec=SPEC)
    assert e.status is EpisodeStatus.EXEC_ERROR and not e.status.is_valid_failure
