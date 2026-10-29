"""Active search: explore, then contract toward nominal (spec 7.4, PROPOSED algorithm).

A deliberately small, inspectable method. Two phases, one episode budget:

1. **Explore.** Sample scenarios uniformly from the declared domain (optionally
   restricted to an approved hypothesis box) until the first valid failure.
   This phase is statistically identical to the random baseline, so any
   advantage must come from phase 2.
2. **Contract.** Keep the nearest failing scenario found so far (the
   incumbent `b`) and the nominal point `x0`. Two moves:
   - *contract*: propose `x0 + a (b - x0)` with `a` the midpoint of the
     interval `(a_lo, 1]`, where `a_lo` is the largest `a` on the current ray
     already seen to pass. A failure shrinks the distance by the factor `a`
     and becomes the incumbent; a pass raises `a_lo`. This is bisection along
     the ray from the incumbent to nominal, so it only helps where failure is
     monotone along that ray. Once `1 - a_lo` falls below `ray_tol` the ray is
     exhausted.
   - *jitter*: propose `b + N(0, sigma * range)` per variable, clipped to the
     bounds. A closer failure becomes the incumbent and resets the ray;
     success widens `sigma`, anything else narrows it (a 1+1 evolution
     strategy with a fifth-rule style step adaptation).
   Every `jitter_every`-th step is a jitter even while the ray is alive, so
   the search does not depend on one ray being monotone.

Everything is driven by one seeded NumPy generator, so the proposal sequence is
reproducible given the same outcomes. No model, no gradient, no surrogate.
"""

from __future__ import annotations

from typing import Annotated

import numpy as np
from pydantic import Field

from skuld.core.protocol import sample_uniform
from skuld.core.schemas import FiniteFloat, PerturbationDomain, SkuldModel
from skuld.search.objective import BudgetExhausted, Candidate, CurvePoint, Ledger, Objective

METHOD_ID = "explore-then-contract-v1"


class ActiveSearchConfig(SkuldModel):
    method: str = METHOD_ID
    budget: Annotated[int, Field(ge=1)]
    sampler_seed: Annotated[int, Field(ge=0)]
    #: optional per-variable [min, max] box the explore phase samples from
    #: (an approved Hypothesis); must lie inside the domain
    explore_box: dict[str, tuple[FiniteFloat, FiniteFloat]] | None = None
    sigma0: Annotated[float, Field(gt=0, le=1)] = 0.25
    sigma_min: Annotated[float, Field(gt=0, le=1)] = 0.02
    sigma_max: Annotated[float, Field(gt=0, le=1)] = 0.5
    sigma_up: Annotated[float, Field(gt=1)] = 1.5
    sigma_down: Annotated[float, Field(gt=0, lt=1)] = 0.7
    ray_tol: Annotated[float, Field(gt=0, lt=1)] = 0.05
    jitter_every: Annotated[int, Field(ge=2)] = 3
    max_exec_errors: Annotated[int, Field(ge=0)] = 5


class SearchResult(SkuldModel):
    method: str
    config: ActiveSearchConfig
    candidates: list[Candidate]
    curve: list[CurvePoint]
    metrics: dict
    best: Candidate | None
    incumbents: list[str]
    explore_episodes: Annotated[int, Field(ge=0)]
    contract_episodes: Annotated[int, Field(ge=0)]


def _check_box(domain: PerturbationDomain, box: dict[str, tuple[float, float]]) -> None:
    for name, (lo, hi) in box.items():
        spec = domain.spec(name)  # KeyError for a name outside the allowlist
        if not (spec.min <= lo < hi <= spec.max):
            raise ValueError(
                f"explore box for {name} [{lo}, {hi}] not inside [{spec.min}, {spec.max}]"
            )


def _sample_explore(
    domain: PerturbationDomain, rng: np.random.Generator, box: dict | None
) -> dict[str, float]:
    vals = sample_uniform(domain, rng)
    if box:
        for name, (lo, hi) in box.items():
            vals[name] = float(rng.uniform(lo, hi))
    return vals


def _clip(domain: PerturbationDomain, vals: dict[str, float]) -> dict[str, float]:
    return {v.name: float(min(max(vals[v.name], v.min), v.max)) for v in domain.variables}


def active_search(
    domain: PerturbationDomain, run: Objective, cfg: ActiveSearchConfig, *, prefix: str = "act"
) -> SearchResult:
    if cfg.explore_box:
        _check_box(domain, cfg.explore_box)
    rng = np.random.default_rng(cfg.sampler_seed)
    ledger = Ledger(domain, run, cfg.budget, prefix, max_exec_errors=cfg.max_exec_errors)
    x0 = domain.nominal_values()
    incumbents: list[str] = []
    best: Candidate | None = None
    explore_n = 0
    seed = 0

    try:
        # ---- phase 1: explore -------------------------------------------------
        while best is None and ledger.remaining > 0:
            vals = _sample_explore(domain, rng, cfg.explore_box)
            c = ledger.evaluate(vals, phase="explore", move="uniform", seed=seed)
            seed += 1
            if c.counts_against_budget:
                explore_n += 1
            if c.valid_failure:
                best = c
                ledger.accept(c)
                incumbents.append(c.scenario_id)

        # ---- phase 2: contract toward nominal ---------------------------------
        a_lo = 0.0
        sigma = cfg.sigma0
        k = 0
        while best is not None and ledger.remaining > 0:
            ray_alive = (1.0 - a_lo) >= cfg.ray_tol
            jitter_turn = (k % cfg.jitter_every) == cfg.jitter_every - 1
            if ray_alive and not jitter_turn:
                a = 0.5 * (a_lo + 1.0)
                vals = {n: x0[n] + a * (best.values[n] - x0[n]) for n in x0}
                c = ledger.evaluate(
                    vals,
                    phase="contract",
                    move="contract",
                    seed=seed,
                    parent=best.scenario_id,
                    note=f"a={a:.4f} a_lo={a_lo:.4f}",
                )
                if not c.counts_against_budget:
                    pass  # EXEC_ERROR: learn nothing, try again
                elif c.valid_failure and c.distance_from_nominal < best.distance_from_nominal:
                    a_lo = a_lo / a  # the known pass point, rescaled onto the shorter ray
                    best = c
                    ledger.accept(c)
                    incumbents.append(c.scenario_id)
                else:
                    a_lo = a
            else:
                noise = {v.name: float(rng.normal(0.0, sigma * v.range)) for v in domain.variables}
                vals = _clip(domain, {n: best.values[n] + noise[n] for n in x0})
                c = ledger.evaluate(
                    vals,
                    phase="contract",
                    move="jitter",
                    seed=seed,
                    parent=best.scenario_id,
                    note=f"sigma={sigma:.4f}",
                )
                if not c.counts_against_budget:
                    pass
                elif c.valid_failure and c.distance_from_nominal < best.distance_from_nominal:
                    best = c
                    ledger.accept(c)
                    incumbents.append(c.scenario_id)
                    a_lo = 0.0
                    sigma = min(sigma * cfg.sigma_up, cfg.sigma_max)
                else:
                    sigma = max(sigma * cfg.sigma_down, cfg.sigma_min)
            seed += 1
            k += 1
    except BudgetExhausted:
        pass

    return SearchResult(
        method=cfg.method,
        config=cfg,
        candidates=ledger.candidates,
        curve=ledger.curve,
        metrics=ledger.metrics(),
        best=ledger.best_failure(),
        incumbents=incumbents,
        explore_episodes=explore_n,
        contract_episodes=ledger.episodes_used - explore_n,
    )
