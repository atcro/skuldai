"""The release gate: a pure, fail-closed decision over stored evidence (spec 6.3, 9).

`decide` never runs anything. It receives the candidate, the test suite and, for
every scenario in every suite, whatever evidence exists, and returns a
`ReleaseDecision`. Precedence when several things are wrong:

    ERROR > BLOCKED > INCOMPLETE > ELIGIBLE

- ERROR: the evidence cannot be trusted: corrupt or missing artifact behind a
  result, checksum mismatch, INVALID or EXEC_ERROR verdicts, a result that names
  a different policy, scenario or spec than the candidate was tested against.
- BLOCKED: a verified TASK_FAIL or SAFETY_FAIL in a required suite.
- INCOMPLETE: a required scenario has no result, or its recording ended before
  the deadline (TIMEOUT: the policy was not given its full chance).
- ELIGIBLE: every scenario in all three suites has a verified PASS. "Eligible"
  means "passed the named simulation suite", never "safe".

Every reason is a sentence naming the suite and scenario, so the UI can show
exactly why a release did not go out. No LLM output reaches this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from skuld.core.schemas import (
    REQUIRED_SUITES,
    EpisodeResult,
    EpisodeStatus,
    ReleaseCandidate,
    ReleaseDecision,
    ReleaseStatus,
    SkuldModel,
    SuiteOutcome,
)
from skuld.release.registry import TestSuite


class CaseEvidence(SkuldModel):
    """What the gate knows about one scenario of one suite."""

    scenario_id: str
    result: EpisodeResult | None = None
    #: None = not checked; False = artifact missing, unreadable or checksum mismatch
    artifact_ok: bool | None = None
    note: str = ""


def decide(
    candidate: ReleaseCandidate,
    suite: TestSuite,
    evidence: dict[str, list[CaseEvidence]],
    *,
    decided_at: datetime | None = None,
) -> ReleaseDecision:
    errors: list[str] = []
    blocks: list[str] = []
    incomplete: list[str] = []
    outcomes: list[SuiteOutcome] = []

    if candidate.test_suite_ref != suite.ref:
        errors.append(
            f"candidate names test suite {candidate.test_suite_ref!r} but the gate was given "
            f"{suite.ref!r}"
        )

    for name in REQUIRED_SUITES:
        expected = suite.scenarios(name)
        given = {e.scenario_id: e for e in evidence.get(name, [])}
        extra = sorted(set(given) - {s.scenario_id for s in expected})
        if extra:
            errors.append(f"{name}: results for scenarios not in the suite: {extra}")
        refs: list[str] = []
        statuses: list[EpisodeStatus] = []
        for sc in expected:
            e = given.get(sc.scenario_id)
            if e is not None and e.result is None and e.artifact_ok is False:
                # evidence exists but is unusable (unreadable, schema-refused, bad checksum):
                # corrupt evidence, not a case that was never run
                errors.append(
                    f"{name}/{sc.scenario_id}: artifact present but unusable"
                    + (f" ({e.note})" if e.note else "")
                )
                continue
            if e is None or e.result is None:
                incomplete.append(f"{name}/{sc.scenario_id}: not executed (no result)")
                continue
            r = e.result
            if e.artifact_ok is False:
                errors.append(
                    f"{name}/{sc.scenario_id}: artifact missing, unreadable or checksum mismatch"
                    + (f" ({e.note})" if e.note else "")
                )
            if r.policy_ref != candidate.policy_ref:
                errors.append(
                    f"{name}/{sc.scenario_id}: result is for policy {r.policy_ref!r}, candidate "
                    f"is {candidate.policy_ref!r} (stale policy)"
                )
            if r.scenario_ref != sc.scenario_id:
                errors.append(f"{name}/{sc.scenario_id}: result names scenario {r.scenario_ref!r}")
            if r.spec_ref != suite.spec_ref:
                errors.append(
                    f"{name}/{sc.scenario_id}: judged under spec {r.spec_ref!r}, suite requires "
                    f"{suite.spec_ref!r}"
                )
            if r.status in (EpisodeStatus.INVALID, EpisodeStatus.EXEC_ERROR):
                errors.append(f"{name}/{sc.scenario_id}: {r.status.value}: {r.detail[:200]}")
            elif r.status is EpisodeStatus.TIMEOUT:
                incomplete.append(
                    f"{name}/{sc.scenario_id}: TIMEOUT, recording ends before the deadline"
                )
            elif r.status.is_valid_failure:
                rules = ", ".join(v.rule for v in r.violations) or "unspecified"
                blocks.append(f"{name}/{sc.scenario_id}: {r.status.value} ({rules})")
            refs.append(r.episode_id)
            statuses.append(r.status)
        outcomes.append(SuiteOutcome(suite=name, episode_refs=refs, statuses=statuses))

    if errors:
        status, reasons = ReleaseStatus.ERROR, errors + blocks + incomplete
    elif blocks:
        status, reasons = ReleaseStatus.BLOCKED, blocks + incomplete
    elif incomplete:
        status, reasons = ReleaseStatus.INCOMPLETE, incomplete
    else:
        status, reasons = ReleaseStatus.ELIGIBLE, []
    return ReleaseDecision(
        candidate_ref=candidate.candidate_id,
        status=status,
        suites=outcomes,
        blocking_reasons=reasons,
        decided_at=decided_at or datetime.now(UTC),
    )
