"""Objective(x) and the candidate ledger shared by every search strategy (spec 7.4).

The objective is whatever runs the policy on a scenario and returns an oracle
status. The search code never looks inside a trajectory and never judges
anything itself: it only reads `EpisodeStatus` and the domain distance. Every
candidate it proposes is written to a ledger, including the ones that pass,
error out or are rejected, so a reviewer can replay the whole decision path.

Budget accounting (spec 7.4): only episodes that produced a terminal verdict
other than EXEC_ERROR count against the episode budget. EXEC_ERROR episodes are
logged and counted separately, and a cap on them stops a broken simulator from
looping forever.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field

from skuld.core.schemas import EpisodeStatus, FiniteFloat, PerturbationDomain, SkuldModel


@dataclass(frozen=True)
class Outcome:
    """What the objective returns for one candidate. Nothing here is a decision."""

    status: EpisodeStatus
    robustness: float | None = None
    wallclock_s: float = 0.0

    @property
    def is_valid_failure(self) -> bool:
        return self.status.is_valid_failure


#: run(values, scenario_id, seed) -> Outcome
Objective = Callable[[Mapping[str, float], str, int], Outcome]


class Candidate(SkuldModel):
    """One ledger row. `accepted` means the strategy adopted it as its new incumbent."""

    index: Annotated[int, Field(ge=0)]
    phase: str
    move: str
    scenario_id: str
    seed: Annotated[int, Field(ge=0)]
    values: dict[str, FiniteFloat]
    status: EpisodeStatus
    valid_failure: bool
    distance_from_nominal: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    robustness: FiniteFloat | None = None
    parent: str | None = None
    accepted: bool = False
    counts_against_budget: bool = True
    wallclock_s: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0.0
    note: str = ""


class CurvePoint(SkuldModel):
    cumulative_episodes: Annotated[int, Field(ge=0)]
    valid_failures_found: Annotated[int, Field(ge=0)]
    running_min_distance: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    cumulative_wallclock_s: Annotated[float, Field(ge=0, allow_inf_nan=False)]


class BudgetExhausted(RuntimeError):
    pass


class TooManyExecErrors(RuntimeError):
    pass


@dataclass
class Ledger:
    """Runs the objective, enforces the budget and records every candidate."""

    domain: PerturbationDomain
    run: Objective
    budget: int
    prefix: str
    max_exec_errors: int = 5
    candidates: list[Candidate] = field(default_factory=list)
    curve: list[CurvePoint] = field(default_factory=list)
    episodes_used: int = 0
    exec_errors: int = 0
    valid_failures: int = 0
    running_min: float = math.inf
    cumulative_wallclock_s: float = 0.0
    first_failure_index: int | None = None
    first_failure_wallclock_s: float | None = None

    @property
    def remaining(self) -> int:
        return self.budget - self.episodes_used

    def evaluate(
        self,
        values: Mapping[str, float],
        *,
        phase: str,
        move: str,
        seed: int,
        parent: str | None = None,
        note: str = "",
    ) -> Candidate:
        if self.remaining <= 0:
            raise BudgetExhausted(f"{self.prefix}: budget of {self.budget} episodes used")
        self.domain.check_values(values)  # a strategy must never leave the declared domain
        vals = {k: float(values[k]) for k in sorted(values)}
        scenario_id = f"{self.prefix}-{len(self.candidates):03d}"
        out = self.run(vals, scenario_id, seed)
        dist = self.domain.distance(vals)
        counts = out.status is not EpisodeStatus.EXEC_ERROR
        cand = Candidate(
            index=len(self.candidates),
            phase=phase,
            move=move,
            scenario_id=scenario_id,
            seed=seed,
            values=vals,
            status=out.status,
            valid_failure=out.is_valid_failure,
            distance_from_nominal=dist,
            robustness=out.robustness,
            parent=parent,
            counts_against_budget=counts,
            wallclock_s=out.wallclock_s,
            note=note,
        )
        self.candidates.append(cand)
        self.cumulative_wallclock_s += out.wallclock_s
        if not counts:
            self.exec_errors += 1
            if self.exec_errors > self.max_exec_errors:
                raise TooManyExecErrors(
                    f"{self.prefix}: {self.exec_errors} EXEC_ERROR episodes; simulator unusable"
                )
            return cand
        self.episodes_used += 1
        if cand.valid_failure:
            self.valid_failures += 1
            self.running_min = min(self.running_min, dist)
            if self.first_failure_index is None:
                self.first_failure_index = self.episodes_used
                self.first_failure_wallclock_s = self.cumulative_wallclock_s
        self.curve.append(
            CurvePoint(
                cumulative_episodes=self.episodes_used,
                valid_failures_found=self.valid_failures,
                running_min_distance=None if math.isinf(self.running_min) else self.running_min,
                cumulative_wallclock_s=round(self.cumulative_wallclock_s, 3),
            )
        )
        return cand

    def accept(self, cand: Candidate) -> None:
        self.candidates[cand.index] = cand.model_copy(update={"accepted": True})

    def metrics(self) -> dict:
        """The protocol's primary metrics, in the same shape as evidence/G07/metrics.json."""
        statuses = [c.status.value for c in self.candidates if c.counts_against_budget]
        return {
            "episodes_to_first_valid_failure": self.first_failure_index,
            "valid_failures_within_budget": self.valid_failures,
            "min_distance_from_nominal_among_valid_failures": None
            if math.isinf(self.running_min)
            else self.running_min,
            "wallclock_s_to_first_valid_failure": None
            if self.first_failure_wallclock_s is None
            else round(self.first_failure_wallclock_s, 2),
            "budget": self.budget,
            "episodes_used": self.episodes_used,
            "exec_errors_not_counted": self.exec_errors,
            "status_counts": {s: statuses.count(s) for s in sorted(set(statuses))},
            "total_wallclock_s": round(self.cumulative_wallclock_s, 1),
        }

    def best_failure(self) -> Candidate | None:
        fails = [c for c in self.candidates if c.valid_failure]
        if not fails:
            return None
        return min(fails, key=lambda c: (c.distance_from_nominal, c.index))
