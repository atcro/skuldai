"""Locked experimental protocol for the MVP (spec 8.1 step 1, runbook G07).

Everything a search strategy will be judged against is fixed here *before* any
strategy runs: domain (with published distance weights), spec, policy, seed
partition, reserved held-out configurations, budgets and the primary metrics.
The protocol is a Pydantic model so its SHA-256 (`PROTOCOL_V1.digest()`) can be
recorded with every result. Changing anything after G07 passes means
`version = 2` and a new lock, never a silent edit.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import numpy as np
from pydantic import Field

from skuld.core.domains import PUSH_V1
from skuld.core.schemas import (
    SCHEMA_VERSION,
    Identifier,
    PerturbationDomain,
    Scenario,
    SchemaVersion,
    Seed,
    SeedLists,
    SkuldModel,
)
from skuld.oracle.specs import PUSH_SPEC_V1

#: must equal skuld.policies.push_controller.POLICY_ID (not imported here: that module needs mujoco)
POLICY_REF = "push-dls-ik-v1"


class Budget(SkuldModel):
    n_nominal: Annotated[int, Field(ge=1)]
    n_random: Annotated[int, Field(ge=1)]
    n_active: Annotated[int, Field(ge=1)]


class SamplerSeeds(SkuldModel):
    """Seeds for the *scenario samplers*. The simulator itself is deterministic (G05)."""

    random_baseline: Seed
    active_search: Seed
    held_out_configs: Seed


class Protocol(SkuldModel):
    schema_version: SchemaVersion = SCHEMA_VERSION
    protocol_id: Identifier
    version: Annotated[int, Field(ge=1)]
    domain: PerturbationDomain
    spec_ref: Identifier
    spec_sha256: str
    policy_ref: Identifier
    seeds: SeedLists
    sampler_seeds: SamplerSeeds
    budget: Budget
    held_out_configs: Annotated[list[Scenario], Field(min_length=1)]
    primary_metrics: Annotated[list[str], Field(min_length=1)]
    locked_at: datetime
    notes: str = ""


def sample_uniform(domain: PerturbationDomain, rng: np.random.Generator) -> dict[str, float]:
    """One scenario drawn uniformly from the domain box. Same RNG state -> same values."""
    return {v.name: float(rng.uniform(v.min, v.max)) for v in domain.variables}


def random_scenarios(
    domain: PerturbationDomain, n: int, *, sampler_seed: int, prefix: str, first_seed: int
) -> list[Scenario]:
    rng = np.random.default_rng(sampler_seed)
    out = []
    for i in range(n):
        out.append(
            Scenario(
                scenario_id=f"{prefix}-{i:03d}",
                domain_ref=domain.domain_id,
                values=sample_uniform(domain, rng),
                seed=first_seed + i,
            )
        )
    return out


_SAMPLER_SEEDS = SamplerSeeds(
    random_baseline=20261026, active_search=20261027, held_out_configs=1000
)
_SEEDS = SeedLists(nominal=[0, 1, 2], regression=[], held_out=[1000, 1001, 1002, 1003, 1004])

PROTOCOL_V1 = Protocol(
    protocol_id="skuld-push-protocol",
    version=1,
    domain=PUSH_V1,
    spec_ref=f"{PUSH_SPEC_V1.spec_id}-v{PUSH_SPEC_V1.version}",
    spec_sha256=PUSH_SPEC_V1.digest(),
    policy_ref=POLICY_REF,
    seeds=_SEEDS,
    sampler_seeds=_SAMPLER_SEEDS,
    # First budget from G05 throughput (unrendered ~0.7 s per 7 s episode, ~1.5 s for a
    # 15 s episode): 25 random + 25 active episodes cost about a minute each. Small
    # samples are a stated limitation (spec 8.1 step 4).
    budget=Budget(n_nominal=3, n_random=25, n_active=25),
    held_out_configs=random_scenarios(
        PUSH_V1,
        5,
        sampler_seed=_SAMPLER_SEEDS.held_out_configs,
        prefix="heldout",
        first_seed=_SEEDS.held_out[0],
    ),
    primary_metrics=[
        "episodes_to_first_valid_failure (lower is better; null if none within budget)",
        "valid_failures_within_budget (TASK_FAIL + SAFETY_FAIL only; INVALID, TIMEOUT and "
        "EXEC_ERROR are excluded)",
        "min_distance_from_nominal_among_valid_failures (domain.distance; lower is better)",
        "wallclock_s_to_first_valid_failure",
        "curve: valid_failures_found vs cumulative_episodes",
        "curve: running_min_distance vs cumulative_episodes",
    ],
    locked_at=datetime(2026, 10, 27, 2, 45, tzinfo=UTC),
    notes=(
        "Simulator and policy are deterministic (G05 bit-identical replay), so a scenario "
        "fails 0 or 1 times out of 1; repeat counts add no information and are not run. "
        "Three nominal runs confirm the policy is worth testing and re-confirm determinism. "
        "Held-out configurations are reserved for release evaluation (G11) and are excluded "
        "from search and repair. Distance weights are all 1.0 (published in domain)."
    ),
)
