"""Skuld data contracts (spec.md section 6).

Every model forbids unknown keys, uses SI units, carries a schema version where it
is persisted, and refuses non-finite numbers. Validation here is structural and
cross-field only; physics, oracle verdicts and release logic live in their own
packages and must never be overridden by anything that arrives in these payloads.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "skuld.schemas.v1"
SchemaVersion = Literal["skuld.schemas.v1"]

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonNegFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PosFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]
UnitInterval = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
]
VariableName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
Seed = Annotated[int, Field(ge=0, lt=2**63)]
Vec3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]

# Scope lock (spec.md section 4.1): at most four perturbation variables.
MAX_PERTURBATION_VARIABLES = 4


class SkuldModel(BaseModel):
    """Base for all contracts: unknown keys are errors, assignment is re-validated."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=False,
    )

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

    def digest(self) -> str:
        """SHA-256 of the canonical JSON. Named `digest` so models may carry a `sha256` field."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- enums


class EpisodeStatus(StrEnum):
    RUNNING = "RUNNING"
    PASS = "PASS"
    TASK_FAIL = "TASK_FAIL"
    SAFETY_FAIL = "SAFETY_FAIL"
    INVALID = "INVALID"
    TIMEOUT = "TIMEOUT"
    EXEC_ERROR = "EXEC_ERROR"

    @property
    def is_valid_failure(self) -> bool:
        """Only these count as failures for search and minimization (spec 6.2)."""
        return self in (EpisodeStatus.TASK_FAIL, EpisodeStatus.SAFETY_FAIL)

    @property
    def is_terminal(self) -> bool:
        return self is not EpisodeStatus.RUNNING


class ReleaseStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    INCOMPLETE = "INCOMPLETE"
    ERROR = "ERROR"


class PolicyKind(StrEnum):
    CLASSICAL = "classical"
    HEURISTIC = "heuristic"
    LEARNED = "learned"


class ViolationKind(StrEnum):
    TASK = "task"
    SAFETY = "safety"


class ApprovalState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactKind(StrEnum):
    RAW = "raw"
    DERIVED = "derived"


# ------------------------------------------------------------- perturbation domain


class VariableSpec(SkuldModel):
    """One allowlisted physical variable with SI unit, bounds and distance weight."""

    name: VariableName
    unit: Annotated[str, Field(min_length=1, max_length=16)]
    nominal: FiniteFloat
    min: FiniteFloat
    max: FiniteFloat
    weight: PosFloat = 1.0

    @model_validator(mode="after")
    def _bounds_ordered(self) -> VariableSpec:
        if not self.min < self.max:
            raise ValueError(f"{self.name}: min ({self.min}) must be < max ({self.max})")
        if not self.min <= self.nominal <= self.max:
            raise ValueError(
                f"{self.name}: nominal ({self.nominal}) must lie within [{self.min}, {self.max}]"
            )
        return self

    @property
    def range(self) -> float:
        return self.max - self.min


class PerturbationDomain(SkuldModel):
    """Frozen allowlist of variables; the only thing a Scenario may vary."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    domain_id: Identifier
    variables: Annotated[
        list[VariableSpec], Field(min_length=1, max_length=MAX_PERTURBATION_VARIABLES)
    ]
    distance_fn: Literal["weighted_normalized_l2"] = "weighted_normalized_l2"

    @field_validator("variables")
    @classmethod
    def _unique_names(cls, variables: list[VariableSpec]) -> list[VariableSpec]:
        names = [v.name for v in variables]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate variable names: {dupes}")
        return variables

    @property
    def names(self) -> frozenset[str]:
        return frozenset(v.name for v in self.variables)

    def spec(self, name: str) -> VariableSpec:
        for v in self.variables:
            if v.name == name:
                return v
        raise KeyError(name)

    def nominal_values(self) -> dict[str, float]:
        return {v.name: v.nominal for v in self.variables}

    def check_values(self, values: Mapping[str, float]) -> None:
        """Raise ValueError unless `values` is a complete, in-bounds assignment."""
        unknown = sorted(set(values) - self.names)
        if unknown:
            raise ValueError(f"variables not in domain {self.domain_id}: {unknown}")
        missing = sorted(self.names - set(values))
        if missing:
            raise ValueError(f"missing variables for domain {self.domain_id}: {missing}")
        for v in self.variables:
            x = values[v.name]
            if not math.isfinite(x):
                raise ValueError(f"{v.name}: non-finite value {x}")
            if not v.min <= x <= v.max:
                raise ValueError(f"{v.name}: {x} outside [{v.min}, {v.max}]")

    def distance(self, values: Mapping[str, float]) -> float:
        """D(x, x0) = sqrt(sum_i w_i * ((x_i - x0_i) / range_i)^2)  (spec 7.2)."""
        self.check_values(values)
        total = 0.0
        for v in self.variables:
            total += v.weight * ((values[v.name] - v.nominal) / v.range) ** 2
        return math.sqrt(total)


class Scenario(SkuldModel):
    """One concrete world configuration plus the seed that makes it replayable."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    scenario_id: Identifier
    domain_ref: Identifier
    values: dict[VariableName, FiniteFloat]
    seed: Seed

    def check_against(self, domain: PerturbationDomain) -> None:
        if domain.domain_id != self.domain_ref:
            raise ValueError(
                f"scenario {self.scenario_id} references domain {self.domain_ref}, "
                f"not {domain.domain_id}"
            )
        domain.check_values(self.values)

    def distance_from_nominal(self, domain: PerturbationDomain) -> float:
        self.check_against(domain)
        return domain.distance(self.values)


# ------------------------------------------------------------------- test spec


class GoalCondition(SkuldModel):
    description: Annotated[str, Field(min_length=1)]
    target_radius_m: PosFloat
    stability_steps: Annotated[int, Field(ge=1)]


class SafetyRules(SkuldModel):
    collision_forbidden: bool = True
    # (x_min, x_max, y_min, y_max, z_min, z_max) in metres, world frame
    workspace_limits_m: (
        tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] | None
    ) = None
    force_telemetry_available: bool = False
    force_limit_n: PosFloat | None = None

    @model_validator(mode="after")
    def _consistent(self) -> SafetyRules:
        if self.force_limit_n is not None and not self.force_telemetry_available:
            # spec 7.3: never report a force limit the simulator cannot measure
            raise ValueError("force_limit_n requires force_telemetry_available=True")
        if self.workspace_limits_m is not None:
            lows = self.workspace_limits_m[0::2]
            highs = self.workspace_limits_m[1::2]
            for axis, lo, hi in zip("xyz", lows, highs, strict=True):
                if not lo < hi:
                    raise ValueError(f"workspace {axis}: min {lo} must be < max {hi}")
        return self


class TestSpec(SkuldModel):
    """Human-approved, versioned requirement set. The only source of thresholds."""

    __test__ = False  # not a pytest test class despite the name

    schema_version: SchemaVersion = SCHEMA_VERSION
    spec_id: Identifier
    version: Annotated[int, Field(ge=1)]
    task: Annotated[str, Field(min_length=1)]
    goal: GoalCondition
    deadline_s: PosFloat
    safety: SafetyRules
    approved_by: str | None = None
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def _approval_pair(self) -> TestSpec:
        if (self.approved_by is None) != (self.approved_at is None):
            raise ValueError("approved_by and approved_at must be set together")
        return self

    @property
    def is_approved(self) -> bool:
        return self.approved_by is not None


# ----------------------------------------------------------- per-step telemetry


class Observation(SkuldModel):
    step: Annotated[int, Field(ge=0)]
    sim_time_s: NonNegFloat
    # sim time at which the observed state was captured; <= sim_time_s when delayed
    source_sim_time_s: NonNegFloat
    delay_applied_ms: NonNegFloat = 0.0
    values: Annotated[list[FiniteFloat], Field(min_length=1)]

    @model_validator(mode="after")
    def _causal(self) -> Observation:
        if self.source_sim_time_s > self.sim_time_s + 1e-12:
            raise ValueError("observation cannot come from the future")
        return self


class Action(SkuldModel):
    step: Annotated[int, Field(ge=0)]
    sim_time_s: NonNegFloat
    values: Annotated[list[FiniteFloat], Field(min_length=1)]


class Contact(SkuldModel):
    geom_a: Annotated[str, Field(min_length=1)]
    geom_b: Annotated[str, Field(min_length=1)]
    normal_force_n: NonNegFloat | None = None


class TrajectoryStep(SkuldModel):
    step: Annotated[int, Field(ge=0)]
    sim_time_s: NonNegFloat
    qpos: Annotated[list[FiniteFloat], Field(min_length=1)]
    qvel: Annotated[list[FiniteFloat], Field(min_length=1)]
    object_pos_m: Vec3
    ee_pos_m: Vec3
    action: Annotated[list[FiniteFloat], Field(min_length=1)]
    contacts: list[Contact] = Field(default_factory=list)
    observation_delay_ms: NonNegFloat = 0.0


class Trajectory(SkuldModel):
    schema_version: SchemaVersion = SCHEMA_VERSION
    trajectory_id: Identifier
    scenario_ref: Identifier
    policy_ref: Identifier
    sim_name: Annotated[str, Field(min_length=1)]
    sim_version: Annotated[str, Field(min_length=1)]
    scene_sha256: Sha256Hex
    dt_s: PosFloat
    steps: Annotated[list[TrajectoryStep], Field(min_length=1)]

    @field_validator("steps")
    @classmethod
    def _monotone(cls, steps: list[TrajectoryStep]) -> list[TrajectoryStep]:
        nq = len(steps[0].qpos)
        nv = len(steps[0].qvel)
        na = len(steps[0].action)
        prev_t = -1.0
        for i, s in enumerate(steps):
            if s.step != i:
                raise ValueError(f"step index {s.step} at position {i}; must be contiguous from 0")
            if s.sim_time_s < prev_t:
                raise ValueError(f"sim_time_s decreases at step {i}")
            prev_t = s.sim_time_s
            if len(s.qpos) != nq or len(s.qvel) != nv or len(s.action) != na:
                raise ValueError(f"state/action dimension changes at step {i}")
        return steps

    @property
    def duration_s(self) -> float:
        return self.steps[-1].sim_time_s - self.steps[0].sim_time_s


# ------------------------------------------------------------- episode result


class Violation(SkuldModel):
    kind: ViolationKind
    rule: Annotated[str, Field(min_length=1)]
    step: Annotated[int, Field(ge=0)] | None = None
    measured: FiniteFloat | None = None
    limit: FiniteFloat | None = None
    detail: str = ""


class EpisodeResult(SkuldModel):
    """Oracle verdict for one run. Status and violations must agree."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    episode_id: Identifier
    scenario_ref: Identifier
    policy_ref: Identifier
    spec_ref: Identifier
    status: EpisodeStatus
    violations: list[Violation] = Field(default_factory=list)
    robustness: FiniteFloat | None = None
    distance_from_nominal: NonNegFloat
    wallclock_s: NonNegFloat
    artifact_uris: list[str] = Field(default_factory=list)
    correlation_id: Identifier
    detail: str = ""

    @model_validator(mode="after")
    def _status_matches_violations(self) -> EpisodeResult:
        kinds = {v.kind for v in self.violations}
        if self.status is EpisodeStatus.PASS and self.violations:
            raise ValueError("PASS cannot carry violations")
        if self.status is EpisodeStatus.SAFETY_FAIL and ViolationKind.SAFETY not in kinds:
            raise ValueError("SAFETY_FAIL requires at least one safety violation")
        if self.status is EpisodeStatus.TASK_FAIL and ViolationKind.TASK not in kinds:
            raise ValueError("TASK_FAIL requires at least one task violation")
        if self.status is EpisodeStatus.TASK_FAIL and ViolationKind.SAFETY in kinds:
            raise ValueError("a safety violation makes the episode SAFETY_FAIL, not TASK_FAIL")
        if self.status is EpisodeStatus.RUNNING:
            raise ValueError("an EpisodeResult must be terminal")
        return self


# ------------------------------------------------------------ policy manifest

_FORBIDDEN_FOR_NON_LEARNED = re.compile(r"gr00t|groot", re.IGNORECASE)


class PolicyManifest(SkuldModel):
    """Immutable policy identity. `latest.pt` is never an identity (spec 6.1)."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    policy_id: Identifier
    kind: PolicyKind
    description: Annotated[str, Field(min_length=1)]
    control_hz: PosFloat
    source_sha256: Sha256Hex | None = None
    checkpoint_sha256: Sha256Hex | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _identity(self) -> PolicyManifest:
        if self.source_sha256 is None and self.checkpoint_sha256 is None:
            raise ValueError("a policy needs source_sha256 or checkpoint_sha256")
        if self.kind is not PolicyKind.LEARNED and _FORBIDDEN_FOR_NON_LEARNED.search(
            f"{self.policy_id} {self.description}"
        ):
            # CLAUDE.md rule 8: never call a classical/heuristic controller GR00T.
            raise ValueError("only a learned policy may be described as GR00T")
        if self.kind is PolicyKind.LEARNED and self.checkpoint_sha256 is None:
            raise ValueError("a learned policy needs checkpoint_sha256")
        return self


# ---------------------------------------------------------------- hypothesis


class HypothesisVariable(SkuldModel):
    name: VariableName
    min: FiniteFloat
    max: FiniteFloat

    @model_validator(mode="after")
    def _ordered(self) -> HypothesisVariable:
        if not self.min < self.max:
            raise ValueError(f"{self.name}: min must be < max")
        return self


class Hypothesis(SkuldModel):
    """Nemotron's structured proposal. It can suggest; it cannot decide (spec 5.2)."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    hypothesis: Annotated[str, Field(min_length=1)]
    variables: Annotated[
        list[HypothesisVariable], Field(min_length=1, max_length=MAX_PERTURBATION_VARIABLES)
    ]
    reason_to_test: Annotated[str, Field(min_length=1)]
    expected_failure_signature: Annotated[str, Field(min_length=1)]
    model_id: Annotated[str, Field(min_length=1)]
    request_id: Annotated[str, Field(min_length=1)]
    evidence_refs: list[str] = Field(default_factory=list)

    def check_against(self, domain: PerturbationDomain) -> None:
        """Reject any variable outside the approved allowlist or bounds."""
        for hv in self.variables:
            if hv.name not in domain.names:
                raise ValueError(
                    f"hypothesis variable {hv.name!r} not in domain {domain.domain_id}"
                )
            spec = domain.spec(hv.name)
            if hv.min < spec.min or hv.max > spec.max:
                raise ValueError(
                    f"hypothesis range for {hv.name} [{hv.min}, {hv.max}] exceeds "
                    f"approved bounds [{spec.min}, {spec.max}]"
                )


# ---------------------------------------------------- documented constraint


class DocumentedConstraint(SkuldModel):
    """A sourced fact from Tavily. Untrusted until a human approves it (spec 10)."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    constraint_id: Identifier
    property: VariableName
    value: FiniteFloat
    unit: Annotated[str, Field(min_length=1, max_length=16)]
    source_url: HttpUrl
    quote_or_paraphrase: Annotated[str, Field(min_length=1, max_length=2000)]
    extraction_confidence: UnitInterval
    retrieved_at: datetime
    approval_state: ApprovalState = ApprovalState.PROPOSED
    authorizer: str | None = None
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def _approval(self) -> DocumentedConstraint:
        decided = self.approval_state in (ApprovalState.APPROVED, ApprovalState.REJECTED)
        if decided and (self.authorizer is None or self.approved_at is None):
            raise ValueError(f"{self.approval_state} requires authorizer and approved_at")
        if not decided and (self.authorizer is not None or self.approved_at is not None):
            raise ValueError("a proposed constraint cannot carry an authorizer")
        return self

    @property
    def is_approved(self) -> bool:
        return self.approval_state is ApprovalState.APPROVED


# ------------------------------------------------------------- counterexample


class Counterexample(SkuldModel):
    """A minimized, re-run failure. Rate is observed, never a safety claim."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    counterexample_id: Identifier
    original: Scenario
    minimized: Scenario
    removed_variables: list[VariableName] = Field(default_factory=list)
    kept_variables: Annotated[list[VariableName], Field(min_length=1)]
    replay_seeds: Annotated[list[Seed], Field(min_length=1)]
    replay_runs: Annotated[int, Field(ge=1)]
    replay_failures: Annotated[int, Field(ge=0)]
    replay_video_uri: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Counterexample:
        if self.original.domain_ref != self.minimized.domain_ref:
            raise ValueError("original and minimized scenarios must share a domain")
        if set(self.removed_variables) & set(self.kept_variables):
            raise ValueError("a variable cannot be both removed and kept")
        if self.replay_failures > self.replay_runs:
            raise ValueError("replay_failures cannot exceed replay_runs")
        if self.replay_runs < len(self.replay_seeds):
            raise ValueError("replay_runs must cover every replay seed at least once")
        return self

    @property
    def observed_failure_rate(self) -> float:
        return self.replay_failures / self.replay_runs

    def check_minimized(self, domain: PerturbationDomain) -> None:
        """Minimized must be no farther from nominal than the original."""
        d_orig = self.original.distance_from_nominal(domain)
        d_min = self.minimized.distance_from_nominal(domain)
        if d_min > d_orig + 1e-12:
            raise ValueError(f"minimized distance {d_min} exceeds original {d_orig}")


# --------------------------------------------------------------- release gate


class SeedLists(SkuldModel):
    nominal: Annotated[list[Seed], Field(min_length=1)]
    regression: list[Seed] = Field(default_factory=list)
    held_out: Annotated[list[Seed], Field(min_length=1)]


class ReleaseCandidate(SkuldModel):
    schema_version: SchemaVersion = SCHEMA_VERSION
    candidate_id: Identifier
    policy_ref: Identifier
    sim_name: Annotated[str, Field(min_length=1)]
    sim_version: Annotated[str, Field(min_length=1)]
    test_suite_ref: Identifier
    seed_lists: SeedLists
    commit_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{7,40}$")]


SuiteName = Literal["nominal", "regression", "held_out"]
REQUIRED_SUITES: tuple[SuiteName, ...] = ("nominal", "regression", "held_out")


class SuiteOutcome(SkuldModel):
    suite: SuiteName
    required: bool = True
    episode_refs: list[Identifier] = Field(default_factory=list)
    statuses: list[EpisodeStatus] = Field(default_factory=list)

    @model_validator(mode="after")
    def _aligned(self) -> SuiteOutcome:
        if len(self.episode_refs) != len(self.statuses):
            raise ValueError("episode_refs and statuses must align")
        return self

    @property
    def all_passed(self) -> bool:
        return bool(self.statuses) and all(s is EpisodeStatus.PASS for s in self.statuses)


class ReleaseDecision(SkuldModel):
    """The CI/CD verdict. The schema itself refuses an unbacked ELIGIBLE (spec 6.3)."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    candidate_ref: Identifier
    status: ReleaseStatus
    suites: list[SuiteOutcome] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    decided_at: datetime

    @model_validator(mode="after")
    def _fail_closed(self) -> ReleaseDecision:
        names = [s.suite for s in self.suites]
        if len(set(names)) != len(names):
            raise ValueError("duplicate suite outcomes")
        if self.status is ReleaseStatus.ELIGIBLE:
            if self.blocking_reasons:
                raise ValueError("ELIGIBLE cannot carry blocking reasons")
            by_name = {s.suite: s for s in self.suites}
            for required in REQUIRED_SUITES:
                outcome = by_name.get(required)
                if outcome is None:
                    raise ValueError(f"ELIGIBLE requires the {required} suite to be evaluated")
                if required != "regression" and not outcome.all_passed:
                    raise ValueError(f"ELIGIBLE requires every {required} episode to PASS")
                if required == "regression" and outcome.statuses and not outcome.all_passed:
                    raise ValueError("ELIGIBLE requires every regression episode to PASS")
        elif not self.blocking_reasons:
            raise ValueError(f"{self.status} requires at least one blocking reason")
        return self


# ----------------------------------------------------------- artifact manifest


class ArtifactEntry(SkuldModel):
    path: Annotated[str, Field(min_length=1)]
    sha256: Sha256Hex
    size_bytes: Annotated[int, Field(ge=0)]
    producer: Annotated[str, Field(min_length=1)]
    kind: ArtifactKind


class ArtifactManifest(SkuldModel):
    schema_version: SchemaVersion = SCHEMA_VERSION
    manifest_id: Identifier
    correlation_id: Identifier
    created_at: datetime
    entries: Annotated[list[ArtifactEntry], Field(min_length=1)]

    @field_validator("entries")
    @classmethod
    def _unique_paths(cls, entries: list[ArtifactEntry]) -> list[ArtifactEntry]:
        paths = [e.path for e in entries]
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate artifact paths in manifest")
        return entries

    def entry(self, path: str) -> ArtifactEntry:
        for e in self.entries:
            if e.path == path:
                return e
        raise KeyError(path)
