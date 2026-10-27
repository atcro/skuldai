"""G02 contract tests: unknown keys, bad ranges, malformed data, honesty rules."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from skuld.core.schemas import (
    ApprovalState,
    Counterexample,
    DocumentedConstraint,
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


@pytest.fixture
def domain() -> PerturbationDomain:
    return PerturbationDomain(
        domain_id="push-v1",
        variables=[
            VariableSpec(name="object_mass_kg", unit="kg", nominal=0.1, min=0.05, max=0.5),
            VariableSpec(name="friction_coefficient", unit="1", nominal=0.6, min=0.2, max=1.0),
        ],
    )


def nominal_scenario(domain: PerturbationDomain, seed: int = 7) -> Scenario:
    return Scenario(
        scenario_id=f"nominal-{seed}",
        domain_ref=domain.domain_id,
        values=domain.nominal_values(),
        seed=seed,
    )


# ----------------------------------------------------------------- unknown keys


def test_unknown_key_is_rejected(domain: PerturbationDomain) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Scenario(
            scenario_id="s",
            domain_ref=domain.domain_id,
            values=domain.nominal_values(),
            seed=1,
            safe=True,  # type: ignore[call-arg]
        )


def test_llm_cannot_smuggle_a_safety_verdict_into_a_hypothesis() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Hypothesis.model_validate(
            {
                "hypothesis": "delay interacts with friction",
                "variables": [{"name": "friction_coefficient", "min": 0.2, "max": 0.4}],
                "reason_to_test": "low friction lengthens slides",
                "expected_failure_signature": "overshoot",
                "model_id": "placeholder",
                "request_id": "r1",
                "safe": True,
            }
        )


# ------------------------------------------------------------------ bad ranges


def test_variable_nominal_outside_bounds_is_rejected() -> None:
    with pytest.raises(ValidationError, match="nominal"):
        VariableSpec(name="x", unit="m", nominal=2.0, min=0.0, max=1.0)


def test_variable_min_not_below_max_is_rejected() -> None:
    with pytest.raises(ValidationError, match="min"):
        VariableSpec(name="x", unit="m", nominal=0.5, min=1.0, max=1.0)


def test_scope_lock_caps_domain_at_four_variables() -> None:
    too_many = [
        VariableSpec(name=f"v{i}", unit="1", nominal=0.0, min=-1.0, max=1.0) for i in range(5)
    ]
    with pytest.raises(ValidationError, match="at most 4"):
        PerturbationDomain(domain_id="d", variables=too_many)


def test_scenario_value_outside_domain_is_rejected(domain: PerturbationDomain) -> None:
    s = Scenario(
        scenario_id="hot",
        domain_ref=domain.domain_id,
        values={"object_mass_kg": 5.0, "friction_coefficient": 0.6},
        seed=1,
    )
    with pytest.raises(ValueError, match="outside"):
        s.check_against(domain)


def test_scenario_unknown_variable_is_rejected(domain: PerturbationDomain) -> None:
    s = Scenario(
        scenario_id="cam",
        domain_ref=domain.domain_id,
        values={**domain.nominal_values(), "camera_yaw_deg": 3.0},
        seed=1,
    )
    with pytest.raises(ValueError, match="not in domain"):
        s.check_against(domain)


def test_hypothesis_range_beyond_approved_bounds_is_rejected(domain: PerturbationDomain) -> None:
    h = Hypothesis(
        hypothesis="heavy objects stall the push",
        variables=[{"name": "object_mass_kg", "min": 0.4, "max": 2.0}],
        reason_to_test="actuator saturation",
        expected_failure_signature="object never reaches target",
        model_id="placeholder",
        request_id="r2",
    )
    with pytest.raises(ValueError, match="exceeds approved bounds"):
        h.check_against(domain)


# -------------------------------------------------------------------- distance


def test_distance_matches_weighted_normalized_l2(domain: PerturbationDomain) -> None:
    values = {"object_mass_kg": 0.5, "friction_coefficient": 0.6}
    expected = math.sqrt(((0.5 - 0.1) / (0.5 - 0.05)) ** 2)
    assert domain.distance(values) == pytest.approx(expected)
    assert domain.distance(domain.nominal_values()) == 0.0


# --------------------------------------------------------------- malformed data


def test_nan_in_trajectory_is_rejected() -> None:
    with pytest.raises(ValidationError, match="finite"):
        TrajectoryStep(
            step=0,
            sim_time_s=0.0,
            qpos=[float("nan")],
            qvel=[0.0],
            object_pos_m=(0.0, 0.0, 0.0),
            ee_pos_m=(0.0, 0.0, 0.0),
            action=[0.0],
        )


def _step(i: int, t: float, nq: int = 2) -> TrajectoryStep:
    return TrajectoryStep(
        step=i,
        sim_time_s=t,
        qpos=[0.0] * nq,
        qvel=[0.0] * nq,
        object_pos_m=(0.0, 0.0, 0.0),
        ee_pos_m=(0.0, 0.0, 0.0),
        action=[0.0],
    )


def test_trajectory_with_time_going_backwards_is_rejected() -> None:
    with pytest.raises(ValidationError, match="decreases"):
        Trajectory(
            trajectory_id="t",
            scenario_ref="s",
            policy_ref="p",
            sim_name="fake",
            sim_version="0",
            scene_sha256=SHA,
            dt_s=0.01,
            steps=[_step(0, 0.0), _step(1, 0.01), _step(2, 0.005)],
        )


def test_trajectory_with_dimension_change_is_rejected() -> None:
    with pytest.raises(ValidationError, match="dimension"):
        Trajectory(
            trajectory_id="t",
            scenario_ref="s",
            policy_ref="p",
            sim_name="fake",
            sim_version="0",
            scene_sha256=SHA,
            dt_s=0.01,
            steps=[_step(0, 0.0, nq=2), _step(1, 0.01, nq=3)],
        )


def test_force_limit_without_force_telemetry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="force_telemetry_available"):
        SafetyRules(force_limit_n=10.0, force_telemetry_available=False)


# --------------------------------------------------------- episode outcomes


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


def test_passing_episode_validates() -> None:
    r = _result(EpisodeStatus.PASS, [])
    assert r.status is EpisodeStatus.PASS
    assert not r.status.is_valid_failure


def test_collision_failure_validates_as_safety_fail() -> None:
    collision = Violation(
        kind=ViolationKind.SAFETY, rule="NEVER collision", step=42, detail="panda_link7 vs table"
    )
    r = _result(EpisodeStatus.SAFETY_FAIL, [collision])
    assert r.status.is_valid_failure


def test_pass_with_a_collision_is_rejected() -> None:
    collision = Violation(kind=ViolationKind.SAFETY, rule="NEVER collision", step=42)
    with pytest.raises(ValidationError, match="PASS cannot carry violations"):
        _result(EpisodeStatus.PASS, [collision])


def test_task_fail_cannot_hide_a_safety_violation() -> None:
    collision = Violation(kind=ViolationKind.SAFETY, rule="NEVER collision", step=1)
    miss = Violation(kind=ViolationKind.TASK, rule="EVENTUALLY object_in_target", step=900)
    with pytest.raises(ValidationError, match="SAFETY_FAIL, not TASK_FAIL"):
        _result(EpisodeStatus.TASK_FAIL, [collision, miss])


def test_running_is_not_a_result() -> None:
    with pytest.raises(ValidationError, match="terminal"):
        _result(EpisodeStatus.RUNNING, [])


# ---------------------------------------------------------- honesty rules


def test_classical_policy_cannot_be_called_groot() -> None:
    with pytest.raises(ValidationError, match="GR00T"):
        PolicyManifest(
            policy_id="push-pd-v1",
            kind=PolicyKind.CLASSICAL,
            description="GR00T N1.7 fine-tuned push policy",
            control_hz=50.0,
            source_sha256=SHA,
            created_at=NOW,
        )


def test_policy_needs_an_identity_hash() -> None:
    with pytest.raises(ValidationError, match="sha256"):
        PolicyManifest(
            policy_id="push-pd-v1",
            kind=PolicyKind.CLASSICAL,
            description="PD Cartesian push controller",
            control_hz=50.0,
            created_at=NOW,
        )


def test_approved_constraint_needs_an_authorizer() -> None:
    with pytest.raises(ValidationError, match="authorizer"):
        DocumentedConstraint(
            constraint_id="c1",
            property="object_mass_kg",
            value=3.0,
            unit="kg",
            source_url="https://example.com/spec",
            quote_or_paraphrase="max payload 3 kg",
            extraction_confidence=0.9,
            retrieved_at=NOW,
            approval_state=ApprovalState.APPROVED,
        )


def test_test_spec_approval_fields_travel_together() -> None:
    with pytest.raises(ValidationError, match="together"):
        TestSpec(
            spec_id="push-spec",
            version=1,
            task="push block into target",
            goal=GoalCondition(description="in target", target_radius_m=0.03, stability_steps=50),
            deadline_s=12.0,
            safety=SafetyRules(),
            approved_by="adam",
        )


# ------------------------------------------------------------- release gate


def test_release_cannot_be_eligible_without_held_out_suite() -> None:
    with pytest.raises(ValidationError, match="held_out"):
        ReleaseDecision(
            candidate_ref="rc1",
            status=ReleaseStatus.ELIGIBLE,
            suites=[
                SuiteOutcome(suite="nominal", episode_refs=["e1"], statuses=[EpisodeStatus.PASS]),
                SuiteOutcome(suite="regression"),
            ],
            decided_at=NOW,
        )


def test_release_cannot_be_eligible_with_a_failing_regression() -> None:
    with pytest.raises(ValidationError, match="regression episode to PASS"):
        ReleaseDecision(
            candidate_ref="rc1",
            status=ReleaseStatus.ELIGIBLE,
            suites=[
                SuiteOutcome(suite="nominal", episode_refs=["e1"], statuses=[EpisodeStatus.PASS]),
                SuiteOutcome(
                    suite="regression", episode_refs=["cx1"], statuses=[EpisodeStatus.SAFETY_FAIL]
                ),
                SuiteOutcome(suite="held_out", episode_refs=["h1"], statuses=[EpisodeStatus.PASS]),
            ],
            decided_at=NOW,
        )


def test_blocked_needs_a_reason() -> None:
    with pytest.raises(ValidationError, match="blocking reason"):
        ReleaseDecision(candidate_ref="rc1", status=ReleaseStatus.BLOCKED, decided_at=NOW)


def test_eligible_with_all_suites_green_validates() -> None:
    d = ReleaseDecision(
        candidate_ref="rc1",
        status=ReleaseStatus.ELIGIBLE,
        suites=[
            SuiteOutcome(suite="nominal", episode_refs=["e1"], statuses=[EpisodeStatus.PASS]),
            SuiteOutcome(suite="regression", episode_refs=["cx1"], statuses=[EpisodeStatus.PASS]),
            SuiteOutcome(suite="held_out", episode_refs=["h1"], statuses=[EpisodeStatus.PASS]),
        ],
        decided_at=NOW,
    )
    assert d.status is ReleaseStatus.ELIGIBLE


# ------------------------------------------------------------ counterexample


def test_counterexample_minimized_must_not_be_farther(domain: PerturbationDomain) -> None:
    original = Scenario(
        scenario_id="o",
        domain_ref=domain.domain_id,
        values={"object_mass_kg": 0.2, "friction_coefficient": 0.6},
        seed=1,
    )
    farther = Scenario(
        scenario_id="m",
        domain_ref=domain.domain_id,
        values={"object_mass_kg": 0.5, "friction_coefficient": 0.6},
        seed=1,
    )
    cx = Counterexample(
        counterexample_id="cx",
        original=original,
        minimized=farther,
        kept_variables=["object_mass_kg"],
        replay_seeds=[1, 2, 3],
        replay_runs=3,
        replay_failures=3,
    )
    with pytest.raises(ValueError, match="exceeds original"):
        cx.check_minimized(domain)
    assert cx.observed_failure_rate == 1.0


def test_canonical_hash_is_stable_across_key_order(domain: PerturbationDomain) -> None:
    a = nominal_scenario(domain)
    b = Scenario.model_validate(
        {
            "seed": a.seed,
            "values": dict(reversed(list(a.values.items()))),
            "domain_ref": a.domain_ref,
            "scenario_id": a.scenario_id,
        }
    )
    assert a.digest() == b.digest()
    assert len(a.digest()) == 64
