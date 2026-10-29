"""G11: the fail-closed release gate (pure) and the four dashboard surfaces.

Gate cases are the mandatory fault-injection suite of spec 9 and 15, run against
a synthetic all-green record so each fault is isolated: missing case, truncated
recording, corrupt artifact, failed job, stale policy hash, wrong spec, tampered
verdict, and a real violation. The dashboard test renders every surface over the
repository's own evidence folder and checks that nothing green is shown for a
blocked policy.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from skuld.core.protocol import PROTOCOL_V1
from skuld.core.schemas import (
    Counterexample,
    EpisodeResult,
    EpisodeStatus,
    ReleaseCandidate,
    ReleaseStatus,
    Scenario,
    SeedLists,
    Violation,
    ViolationKind,
)
from skuld.oracle.evaluate import exec_error_result
from skuld.oracle.specs import PUSH_SPEC_V1
from skuld.release import CaseEvidence, build_suite, decide, regression_from_counterexample

P = PROTOCOL_V1
D = P.domain
NOW = datetime(2026, 10, 28, tzinfo=UTC)
POLICY = "push-dls-ik-v1"


def _ce() -> Counterexample:
    vals = D.nominal_values()
    orig = dict(vals, observation_delay_ms=140.0, object_mass_kg=0.17)
    mini = dict(vals, observation_delay_ms=140.0)
    return Counterexample(
        counterexample_id="ce-t",
        original=Scenario(scenario_id="act-020", domain_ref=D.domain_id, values=orig, seed=0),
        minimized=Scenario(scenario_id="minimized", domain_ref=D.domain_id, values=mini, seed=0),
        removed_variables=["object_mass_kg"],
        kept_variables=["observation_delay_ms"],
        replay_seeds=[0, 1, 2],
        replay_runs=3,
        replay_failures=3,
    )


SUITE = build_suite(
    P,
    regression_from_counterexample(
        _ce(), source_gate="G10", reproduced_failure="SAFETY_FAIL: NEVER collision", created_at=NOW
    ),
    created_at=NOW,
)
CAND = ReleaseCandidate(
    candidate_id="rc-t",
    policy_ref=POLICY,
    sim_name="mujoco",
    sim_version="3.17.0",
    test_suite_ref=SUITE.ref,
    seed_lists=SeedLists(nominal=P.seeds.nominal, regression=[0], held_out=P.seeds.held_out),
    commit_sha="ada1953",
)


def _result(sc: Scenario, status: EpisodeStatus, **kw) -> EpisodeResult:
    violations = []
    if status is EpisodeStatus.SAFETY_FAIL:
        violations = [Violation(kind=ViolationKind.SAFETY, rule="NEVER collision", step=170)]
    fields = dict(
        episode_id=f"traj-{sc.scenario_id}-s{sc.seed}",
        scenario_ref=sc.scenario_id,
        policy_ref=POLICY,
        spec_ref=SUITE.spec_ref,
        status=status,
        violations=violations,
        distance_from_nominal=sc.distance_from_nominal(D),
        wallclock_s=0.5,
        correlation_id=f"traj-{sc.scenario_id}-s{sc.seed}",
    )
    fields.update(kw)
    return EpisodeResult(**fields)


def green() -> dict[str, list[CaseEvidence]]:
    return {
        s: [
            CaseEvidence(
                scenario_id=sc.scenario_id, result=_result(sc, EpisodeStatus.PASS), artifact_ok=True
            )
            for sc in SUITE.scenarios(s)
        ]
        for s in ("nominal", "regression", "held_out")
    }


def test_suite_registry_is_built_from_protocol_and_counterexample() -> None:
    assert [s.scenario_id for s in SUITE.nominal] == ["nominal-s0", "nominal-s1", "nominal-s2"]
    assert [t.test_id for t in SUITE.regression] == ["reg-ce-t-minimized", "reg-ce-t-original"]
    assert SUITE.held_out == P.held_out_configs
    assert SUITE.protocol_sha256 == P.digest() and SUITE.ref.startswith("skuld-push-protocol")
    # a counterexample that never failed on replay cannot become a regression test
    never = _ce().model_copy(update={"replay_failures": 0})
    with pytest.raises(ValueError, match="never failed"):
        regression_from_counterexample(
            never, source_gate="G10", reproduced_failure="x", created_at=NOW
        )
    assert decide(CAND, SUITE, green(), decided_at=NOW).status is ReleaseStatus.ELIGIBLE


@pytest.mark.parametrize(
    "fault, expected, reason_fragment",
    [
        ("missing_case", ReleaseStatus.INCOMPLETE, "not executed"),
        ("timeout", ReleaseStatus.INCOMPLETE, "TIMEOUT"),
        ("violation", ReleaseStatus.BLOCKED, "SAFETY_FAIL (NEVER collision)"),
        ("corrupt_artifact", ReleaseStatus.ERROR, "checksum mismatch"),
        ("failed_job", ReleaseStatus.ERROR, "EXEC_ERROR"),
        ("invalid_telemetry", ReleaseStatus.ERROR, "INVALID"),
        ("stale_policy", ReleaseStatus.ERROR, "stale policy"),
        ("wrong_spec", ReleaseStatus.ERROR, "judged under spec"),
        ("foreign_scenario", ReleaseStatus.ERROR, "not in the suite"),
        ("wrong_suite_ref", ReleaseStatus.ERROR, "names test suite"),
        ("schema_refused_result", ReleaseStatus.ERROR, "present but unusable"),
        ("violation_plus_missing", ReleaseStatus.BLOCKED, "SAFETY_FAIL"),
        ("error_plus_violation", ReleaseStatus.ERROR, "stale policy"),
    ],
)
def test_gate_fails_closed(fault: str, expected: ReleaseStatus, reason_fragment: str) -> None:
    ev = green()
    cand = CAND
    h0 = SUITE.held_out[0]
    if fault == "missing_case":
        ev["held_out"] = ev["held_out"][1:]
    elif fault == "timeout":
        ev["held_out"][0] = CaseEvidence(
            scenario_id=h0.scenario_id, result=_result(h0, EpisodeStatus.TIMEOUT), artifact_ok=True
        )
    elif fault in ("violation", "violation_plus_missing"):
        r = SUITE.regression[0].scenario
        ev["regression"][0] = CaseEvidence(
            scenario_id=r.scenario_id,
            result=_result(r, EpisodeStatus.SAFETY_FAIL),
            artifact_ok=True,
        )
        if fault == "violation_plus_missing":
            ev["held_out"] = ev["held_out"][1:]
    elif fault == "corrupt_artifact":
        ev["nominal"][0] = ev["nominal"][0].model_copy(update={"artifact_ok": False})
    elif fault == "failed_job":
        ev["held_out"][0] = CaseEvidence(
            scenario_id=h0.scenario_id,
            result=exec_error_result(
                episode_id="e",
                error="job status unknown",
                spec=PUSH_SPEC_V1,
                scenario_ref=h0.scenario_id,
                policy_ref=POLICY,
            ),
        )
    elif fault == "invalid_telemetry":
        ev["held_out"][0] = CaseEvidence(
            scenario_id=h0.scenario_id, result=_result(h0, EpisodeStatus.INVALID), artifact_ok=True
        )
    elif fault in ("stale_policy", "error_plus_violation"):
        cand = CAND.model_copy(update={"policy_ref": "push-dls-ik-v0"})
        if fault == "error_plus_violation":
            r = SUITE.regression[0].scenario
            ev["regression"][0] = CaseEvidence(
                scenario_id=r.scenario_id, result=_result(r, EpisodeStatus.SAFETY_FAIL)
            )
    elif fault == "wrong_spec":
        n0 = SUITE.nominal[0]
        ev["nominal"][0] = CaseEvidence(
            scenario_id=n0.scenario_id,
            result=_result(n0, EpisodeStatus.PASS, spec_ref="push-block-v0"),
        )
    elif fault == "foreign_scenario":
        sc = Scenario(
            scenario_id="smuggled", domain_ref=D.domain_id, values=D.nominal_values(), seed=9
        )
        ev["held_out"].append(
            CaseEvidence(scenario_id="smuggled", result=_result(sc, EpisodeStatus.PASS))
        )
    elif fault == "wrong_suite_ref":
        cand = CAND.model_copy(update={"test_suite_ref": "some-other-suite"})
    elif fault == "schema_refused_result":
        ev["held_out"][0] = CaseEvidence(
            scenario_id=h0.scenario_id, result=None, artifact_ok=False, note="schema violation"
        )
    d = decide(cand, SUITE, ev, decided_at=NOW)
    assert d.status is expected, d.blocking_reasons
    assert any(reason_fragment in r for r in d.blocking_reasons), d.blocking_reasons
    assert len(d.suites) == 3

    # the schema itself refuses a verdict edited to PASS while violations remain
    r = SUITE.regression[0].scenario
    bad = _result(r, EpisodeStatus.SAFETY_FAIL).model_dump(mode="json")
    bad["status"] = "PASS"
    with pytest.raises(ValidationError):
        EpisodeResult.model_validate(bad)


def test_dashboard_surfaces_render_from_real_records() -> None:
    from skuld.api.main import app

    client = TestClient(app)
    pages = {
        "/": ("Test Lab", "Job ledger"),
        "/atlas?x=observation_delay_ms&y=friction_coefficient": ("Failure Atlas", "nominal"),
        "/counterexample": ("Counterexample Replay", "Original vs minimized"),
        "/release": ("Release Gate", "ELIGIBLE means"),
    }
    for path, needles in pages.items():
        resp = client.get(path)
        assert resp.status_code == 200, path
        for n in needles:
            assert n in resp.text, (path, n)
    # a bad variable pair falls back instead of erroring
    assert client.get("/atlas?x=nope&y=nope").status_code == 200
    # the release page never shows the policy under test as eligible while its
    # own counterexample is a stored regression (G11 evidence, when present)
    rel = client.get("/release").text
    cards = [c for c in rel.split('<div class="card"') if "rc-push-dls-ik-v1" in c]
    for card in cards:
        assert "status-big ELIGIBLE" not in card and "status-big BLOCKED" in card
    assert client.get("/health").json()["status"] == "ok"
