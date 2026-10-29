"""G02 contract tests: unknown keys, bad ranges, malformed data, honesty rules.

One table of refusals (each row builds something the schema must reject), plus the
two checks that are not refusals (distance, digest) and the counterexample rule.
Positive paths are not repeated here: the oracle, release, search, Tavily and Token
Factory tests build these objects on real code paths. Checks that other tests already
make (hypothesis bounds, approval smuggling, extra keys on trajectories) are not
duplicated either.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from skuld.core.schemas import (
    Counterexample,
    EpisodeResult,
    EpisodeStatus,
    GoalCondition,
    Hypothesis,
    PerturbationDomain,
    PolicyKind,
    PolicyManifest,
    ReleaseDecision,
    ReleaseStatus,
    SafetyRules,
    Scenario,
    SuiteOutcome,
    TestSpec,
    Trajectory,
    TrajectoryStep,
    VariableSpec,
    Violation,
    ViolationKind,
)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
SHA = "a" * 64
DOMAIN = PerturbationDomain(
    domain_id="push-v1",
    variables=[
        VariableSpec(name="object_mass_kg", unit="kg", nominal=0.1, min=0.05, max=0.5),
        VariableSpec(name="friction_coefficient", unit="1", nominal=0.6, min=0.2, max=1.0),
    ],
)
COLLISION = Violation(kind=ViolationKind.SAFETY, rule="NEVER collision", step=42)
MISS = Violation(kind=ViolationKind.TASK, rule="EVENTUALLY object_in_target", step=900)
GREEN = SuiteOutcome(suite="nominal", episode_refs=["e1"], statuses=[EpisodeStatus.PASS])


def _scenario(values: dict[str, float], scenario_id: str = "s") -> Scenario:
    return Scenario(scenario_id=scenario_id, domain_ref=DOMAIN.domain_id, values=values, seed=1)


def _step(i: int, t: float, nq: int = 2, x: float = 0.0) -> TrajectoryStep:
    return TrajectoryStep(
        step=i,
        sim_time_s=t,
        qpos=[x] * nq,
        qvel=[0.0] * nq,
        object_pos_m=(0.0, 0.0, 0.0),
        ee_pos_m=(0.0, 0.0, 0.0),
        action=[0.0],
    )


def _traj(steps: list[TrajectoryStep]) -> Trajectory:
    return Trajectory(
        trajectory_id="t",
        scenario_ref="s",
        policy_ref="p",
        sim_name="fake",
        sim_version="0",
        scene_sha256=SHA,
        dt_s=0.01,
        steps=steps,
    )


def _result(status: EpisodeStatus, violations: list[Violation]) -> EpisodeResult:
    return EpisodeResult(
        episode_id="e1",
        scenario_ref="s1",
        policy_ref="p1",
        spec_ref="spec1",
        status=status,
        violations=violations,
        distance_from_nominal=0.0,
        wallclock_s=1.0,
        correlation_id="c1",
    )


def _policy(description: str, **kw: object) -> PolicyManifest:
    return PolicyManifest(
        policy_id="push-pd-v1",
        kind=PolicyKind.CLASSICAL,
        description=description,
        control_hz=50.0,
        created_at=NOW,
        **kw,  # type: ignore[arg-type]
    )


def _release(status: ReleaseStatus, suites: list[SuiteOutcome]) -> ReleaseDecision:
    return ReleaseDecision(candidate_ref="rc1", status=status, suites=suites, decided_at=NOW)


def _suite(name: str, status: EpisodeStatus) -> SuiteOutcome:
    return SuiteOutcome(suite=name, episode_refs=[f"{name}-1"], statuses=[status])


REFUSALS: list[tuple[str, Callable[[], object], str]] = [
    (
        "model output cannot smuggle a verdict key into a hypothesis",
        lambda: Hypothesis.model_validate(
            {
                "hypothesis": "delay interacts with friction",
                "variables": [{"name": "friction_coefficient", "min": 0.2, "max": 0.4}],
                "reason_to_test": "low friction lengthens slides",
                "expected_failure_signature": "overshoot",
                "model_id": "placeholder",
                "request_id": "r1",
                "safe": True,
            }
        ),
        "extra_forbidden",
    ),
    (
        "variable nominal outside its bounds",
        lambda: VariableSpec(name="x", unit="m", nominal=2.0, min=0.0, max=1.0),
        "nominal",
    ),
    (
        "variable min not below max",
        lambda: VariableSpec(name="x", unit="m", nominal=0.5, min=1.0, max=1.0),
        "min",
    ),
    (
        "scope lock: five variables",
        lambda: PerturbationDomain(
            domain_id="d",
            variables=[
                VariableSpec(name=f"v{i}", unit="1", nominal=0.0, min=-1.0, max=1.0)
                for i in range(5)
            ],
        ),
        "at most 4",
    ),
    (
        "scenario value outside the domain",
        lambda: _scenario({"object_mass_kg": 5.0, "friction_coefficient": 0.6}).check_against(
            DOMAIN
        ),
        "outside",
    ),
    (
        "scenario with a variable the domain does not have",
        lambda: _scenario({**DOMAIN.nominal_values(), "camera_yaw_deg": 3.0}).check_against(DOMAIN),
        "not in domain",
    ),
    ("NaN in a trajectory step", lambda: _step(0, 0.0, x=float("nan")), "finite"),
    (
        "trajectory time going backwards",
        lambda: _traj([_step(0, 0.0), _step(1, 0.01), _step(2, 0.005)]),
        "decreases",
    ),
    (
        "trajectory state dimension changing mid-run",
        lambda: _traj([_step(0, 0.0, nq=2), _step(1, 0.01, nq=3)]),
        "dimension",
    ),
    (
        "force limit without force telemetry",
        lambda: SafetyRules(force_limit_n=10.0, force_telemetry_available=False),
        "force_telemetry_available",
    ),
    (
        "PASS carrying a collision",
        lambda: _result(EpisodeStatus.PASS, [COLLISION]),
        "PASS cannot carry violations",
    ),
    (
        "TASK_FAIL hiding a safety violation",
        lambda: _result(EpisodeStatus.TASK_FAIL, [COLLISION, MISS]),
        "SAFETY_FAIL, not TASK_FAIL",
    ),
    ("RUNNING offered as a result", lambda: _result(EpisodeStatus.RUNNING, []), "terminal"),
    (
        "classical policy described as GR00T",
        lambda: _policy("GR00T N1.7 fine-tuned push policy", source_sha256=SHA),
        "GR00T",
    ),
    (
        "policy without an identity hash",
        lambda: _policy("PD Cartesian push controller"),
        "sha256",
    ),
    (
        "spec approval fields that do not travel together",
        lambda: TestSpec(
            spec_id="push-spec",
            version=1,
            task="push block into target",
            goal=GoalCondition(description="in target", target_radius_m=0.03, stability_steps=50),
            deadline_s=12.0,
            safety=SafetyRules(),
            approved_by="adam",
        ),
        "together",
    ),
    (
        "release ELIGIBLE without a held-out suite",
        lambda: _release(ReleaseStatus.ELIGIBLE, [GREEN, SuiteOutcome(suite="regression")]),
        "held_out",
    ),
    (
        "release ELIGIBLE with a failing regression",
        lambda: _release(
            ReleaseStatus.ELIGIBLE,
            [
                GREEN,
                _suite("regression", EpisodeStatus.SAFETY_FAIL),
                _suite("held_out", EpisodeStatus.PASS),
            ],
        ),
        "regression episode to PASS",
    ),
    (
        "release BLOCKED without a reason",
        lambda: _release(ReleaseStatus.BLOCKED, []),
        "blocking reason",
    ),
]


@pytest.mark.parametrize(("name", "build", "match"), REFUSALS, ids=[r[0] for r in REFUSALS])
def test_schema_refuses(name: str, build: Callable[[], object], match: str) -> None:
    # pydantic's ValidationError is a ValueError, so one clause covers validators and checks
    with pytest.raises(ValueError, match=match):
        build()


def test_distance_and_digest() -> None:
    expected = math.sqrt(((0.5 - 0.1) / (0.5 - 0.05)) ** 2)
    assert DOMAIN.distance({"object_mass_kg": 0.5, "friction_coefficient": 0.6}) == pytest.approx(
        expected
    )
    assert DOMAIN.distance(DOMAIN.nominal_values()) == 0.0
    a = _scenario(DOMAIN.nominal_values(), "nominal-7")
    b = Scenario.model_validate(
        {
            "seed": a.seed,
            "values": dict(reversed(list(a.values.items()))),
            "domain_ref": a.domain_ref,
            "scenario_id": a.scenario_id,
        }
    )
    assert a.digest() == b.digest() and len(a.digest()) == 64


def test_counterexample_minimized_must_not_be_farther() -> None:
    cx = Counterexample(
        counterexample_id="cx",
        original=_scenario({"object_mass_kg": 0.2, "friction_coefficient": 0.6}, "o"),
        minimized=_scenario({"object_mass_kg": 0.5, "friction_coefficient": 0.6}, "m"),
        kept_variables=["object_mass_kg"],
        replay_seeds=[1, 2, 3],
        replay_runs=3,
        replay_failures=3,
    )
    with pytest.raises(ValueError, match="exceeds original"):
        cx.check_minimized(DOMAIN)
    assert cx.observed_failure_rate == 1.0
