"""Registries the release gate reads: policies, and the test suite (spec 9, G11).

- `PolicyRegistry`: immutable identities (`PolicyManifest`, honest `kind`, source or
  checkpoint hash). A candidate names one of these; the gate checks every stored
  result against that name.
- `TestSuite`: the three mandatory suites. Nominal and held-out scenarios come from
  the locked protocol; regression tests are stored counterexamples. Each stored
  regression carries the counterexample it came from and the failure it reproduced,
  so a reviewer can trace a BLOCKED release back to the evidence that caused it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import Field

from skuld.core.protocol import Protocol
from skuld.core.schemas import (
    SCHEMA_VERSION,
    Counterexample,
    Identifier,
    PolicyManifest,
    Scenario,
    SchemaVersion,
    SkuldModel,
)


class PolicyRegistry(SkuldModel):
    schema_version: SchemaVersion = SCHEMA_VERSION
    policies: Annotated[list[PolicyManifest], Field(min_length=1)]

    def get(self, policy_id: str) -> PolicyManifest:
        for p in self.policies:
            if p.policy_id == policy_id:
                return p
        raise KeyError(policy_id)

    @property
    def ids(self) -> list[str]:
        ids = [p.policy_id for p in self.policies]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate policy ids in registry")
        return ids


class RegressionTest(SkuldModel):
    """A stored counterexample a future policy must pass."""

    test_id: Identifier
    scenario: Scenario
    source_counterexample_id: Identifier
    source_gate: Annotated[str, Field(min_length=1)]
    reproduced_failure: Annotated[str, Field(min_length=1)]  # e.g. "SAFETY_FAIL: NEVER collision"
    replay_runs: Annotated[int, Field(ge=1)]
    replay_failures: Annotated[int, Field(ge=1)]  # a regression test must have failed at least once
    created_at: datetime


class TestSuite(SkuldModel):
    """The three mandatory suites. Scenarios here are the only ones the gate accepts."""

    __test__ = False

    schema_version: SchemaVersion = SCHEMA_VERSION
    suite_id: Identifier
    protocol_sha256: str
    spec_ref: Identifier
    domain_ref: Identifier
    nominal: Annotated[list[Scenario], Field(min_length=1)]
    regression: list[RegressionTest] = Field(default_factory=list)
    held_out: Annotated[list[Scenario], Field(min_length=1)]
    created_at: datetime

    def scenarios(self, suite: str) -> list[Scenario]:
        if suite == "nominal":
            return list(self.nominal)
        if suite == "regression":
            return [t.scenario for t in self.regression]
        if suite == "held_out":
            return list(self.held_out)
        raise KeyError(suite)

    @property
    def ref(self) -> str:
        """Content-addressed: the same scenarios give the same ref whenever the suite is built."""
        content = self.model_copy(update={"created_at": datetime(2000, 1, 1, tzinfo=UTC)})
        return f"{self.suite_id}-{content.digest()[:12]}"


def regression_from_counterexample(
    ce: Counterexample, *, source_gate: str, reproduced_failure: str, created_at: datetime
) -> list[RegressionTest]:
    """Both the original and the minimized scenario become stored tests.

    The minimized one is the sharper test (fewer perturbations); the original is kept
    because it is the scenario the search actually hit.
    """
    if ce.replay_failures < 1:
        raise ValueError("a counterexample that never failed on replay is not a regression test")
    out = []
    for label, sc in (("minimized", ce.minimized), ("original", ce.original)):
        out.append(
            RegressionTest(
                test_id=f"reg-{ce.counterexample_id}-{label}",
                scenario=sc.model_copy(
                    update={"scenario_id": f"reg-{ce.counterexample_id}-{label}"}
                ),
                source_counterexample_id=ce.counterexample_id,
                source_gate=source_gate,
                reproduced_failure=reproduced_failure,
                replay_runs=ce.replay_runs,
                replay_failures=ce.replay_failures,
                created_at=created_at,
            )
        )
    return out


def build_suite(
    protocol: Protocol, regressions: list[RegressionTest], *, created_at: datetime | None = None
) -> TestSuite:
    """Nominal + held-out from the locked protocol, regressions from stored counterexamples."""
    domain = protocol.domain
    nominal = [
        Scenario(
            scenario_id=f"nominal-s{seed}",
            domain_ref=domain.domain_id,
            values=domain.nominal_values(),
            seed=seed,
        )
        for seed in protocol.seeds.nominal
    ]
    for t in regressions:
        t.scenario.check_against(domain)
    ids = [s.scenario_id for s in nominal]
    ids += [t.scenario.scenario_id for t in regressions]
    ids += [s.scenario_id for s in protocol.held_out_configs]
    if len(set(ids)) != len(ids):
        raise ValueError("scenario ids must be unique across suites")
    return TestSuite(
        suite_id=f"{protocol.protocol_id}-suite",
        protocol_sha256=protocol.digest(),
        spec_ref=protocol.spec_ref,
        domain_ref=domain.domain_id,
        nominal=nominal,
        regression=regressions,
        held_out=list(protocol.held_out_configs),
        created_at=created_at or datetime.now(UTC),
    )
