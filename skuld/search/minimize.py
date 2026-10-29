"""Counterexample minimization: greedy revert, then bounded local refinement (spec 7.5).

Input: a scenario known to fail. Output: a scenario that still fails and is no
farther from nominal, with every variable that could be reverted to its nominal
value reverted, and every remaining variable pushed as close to nominal as a
short bisection allows. The result is *locally* minimized under this simulator
and controller. It is never a global minimum and never a causal proof.

Steps, each one logged in the ledger:

1. **confirm**: re-run the initial scenario; it must fail or minimization
   refuses to start.
2. **revert**: variables sorted by normalized distance from nominal, nearest
   first. Each is set to nominal in turn and the candidate is run on every
   seed in `seeds`; it is kept only if it fails on all of them (threshold fixed
   before any outcome is seen). Reverted variables are "removed".
3. **refine**: for each kept variable, bisection between its nominal value
   (known to pass at step 2, under the configuration of that moment) and its
   current value, for at most `refine_steps` evaluations or until the
   normalized interval is below `refine_tol`. Bisection assumes failure is
   monotone along the axis, so:
4. **probe**: one extra episode per refined variable at the midpoint between
   nominal and the closest passing value seen. If it fails, failure is not
   monotone along that axis; the probe is adopted as the new incumbent (it is
   closer) and the variable is reported as non-monotone.

The simulator is deterministic (G05/G07), so `seeds=[s]` is the honest default;
more seeds re-confirm determinism rather than estimate a probability.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from skuld.core.schemas import FiniteFloat, PerturbationDomain, SkuldModel
from skuld.search.objective import Candidate, Ledger, Objective


class MinimizationConfig(SkuldModel):
    seeds: Annotated[list[Annotated[int, Field(ge=0)]], Field(min_length=1)] = [0]
    refine_steps: Annotated[int, Field(ge=0)] = 4
    refine_tol: Annotated[float, Field(gt=0, lt=1)] = 0.02
    probe: bool = True
    max_exec_errors: Annotated[int, Field(ge=0)] = 5


class MinimizationResult(SkuldModel):
    status: str  # "minimized" | "not_reproduced"
    config: MinimizationConfig
    initial_values: dict[str, FiniteFloat]
    minimized_values: dict[str, FiniteFloat]
    initial_distance: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    minimized_distance: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    removed_variables: list[str]
    kept_variables: list[str]
    non_monotone_variables: list[str]
    refined: dict[str, dict]
    candidates: list[Candidate]
    episodes_used: Annotated[int, Field(ge=0)]
    exec_errors: Annotated[int, Field(ge=0)]


class NotAFailure(RuntimeError):
    pass


def _budget(domain: PerturbationDomain, cfg: MinimizationConfig) -> int:
    n = len(domain.variables)
    s = len(cfg.seeds)
    return s * (1 + n + n * cfg.refine_steps + (n if cfg.probe else 0)) + cfg.max_exec_errors


def minimize_failure(
    domain: PerturbationDomain,
    initial: dict[str, float],
    run: Objective,
    cfg: MinimizationConfig | None = None,
    *,
    prefix: str = "min",
) -> MinimizationResult:
    cfg = cfg or MinimizationConfig()
    domain.check_values(initial)
    x0 = domain.nominal_values()
    ledger = Ledger(domain, run, _budget(domain, cfg), prefix, max_exec_errors=cfg.max_exec_errors)

    def fails_on_all_seeds(vals: dict[str, float], *, phase: str, move: str, parent, note):
        """Run on every seed; True only if every counted run is a valid failure."""
        ok = True
        last = None
        for s in cfg.seeds:
            c = ledger.evaluate(vals, phase=phase, move=move, seed=s, parent=parent, note=note)
            while not c.counts_against_budget:  # EXEC_ERROR: retry this seed (capped by ledger)
                c = ledger.evaluate(
                    vals, phase=phase, move=move, seed=s, parent=parent, note=note + " retry"
                )
            last = c
            ok = ok and c.valid_failure
        if ok:  # adopted configuration: mark every seed's run as accepted in the ledger
            for cand in ledger.candidates[-len(cfg.seeds) :]:
                ledger.accept(cand)
        return ok, last

    def norm_dev(vals: dict[str, float], name: str) -> float:
        v = domain.spec(name)
        return abs(vals[name] - v.nominal) / v.range

    # ---- 1. confirm -------------------------------------------------------
    ok, c = fails_on_all_seeds(dict(initial), phase="confirm", move="replay", parent=None, note="")
    base_fields = dict(
        config=cfg,
        initial_values=dict(initial),
        initial_distance=domain.distance(initial),
        removed_variables=[],
        non_monotone_variables=[],
        refined={},
    )
    if not ok:
        return MinimizationResult(
            status="not_reproduced",
            minimized_values=dict(initial),
            minimized_distance=domain.distance(initial),
            kept_variables=sorted(initial),
            candidates=ledger.candidates,
            episodes_used=ledger.episodes_used,
            exec_errors=ledger.exec_errors,
            **base_fields,
        )
    best = dict(initial)
    best_id = c.scenario_id

    # ---- 2. greedy revert, nearest-to-nominal variable first ------------------
    removed, kept = [], []
    order = sorted(best, key=lambda k: norm_dev(best, k))
    for name in order:
        if best[name] == x0[name]:
            removed.append(name)  # already nominal: nothing to revert
            continue
        cand = dict(best)
        cand[name] = x0[name]
        ok, c = fails_on_all_seeds(
            cand, phase="revert", move=f"revert:{name}", parent=best_id, note=""
        )
        if ok:
            best, best_id = cand, c.scenario_id
            removed.append(name)
        else:
            kept.append(name)

    # ---- 3. refine each kept variable toward nominal (bisection) --------------
    refined: dict[str, dict] = {}
    non_monotone: list[str] = []
    for name in kept:
        v = domain.spec(name)
        lo = x0[name]  # passed at step 2 (with the other variables as they were then)
        hi = best[name]  # fails
        steps = 0
        while steps < cfg.refine_steps and abs(hi - lo) / v.range >= cfg.refine_tol:
            mid = 0.5 * (lo + hi)
            cand = dict(best)
            cand[name] = mid
            ok, c = fails_on_all_seeds(
                cand,
                phase="refine",
                move=f"bisect:{name}",
                parent=best_id,
                note=f"lo={lo:.6g} hi={hi:.6g}",
            )
            steps += 1
            if ok:
                hi = mid
                best, best_id = cand, c.scenario_id
            else:
                lo = mid
        info = {"from": initial[name], "to": best[name], "pass_bound": lo, "bisections": steps}
        # ---- 4. monotonicity probe: a point closer to nominal than any pass seen
        if cfg.probe and lo != x0[name]:
            probe_val = 0.5 * (x0[name] + lo)
            cand = dict(best)
            cand[name] = probe_val
            ok, c = fails_on_all_seeds(
                cand,
                phase="probe",
                move=f"probe:{name}",
                parent=best_id,
                note=f"pass_bound={lo:.6g}",
            )
            info["probe_value"] = probe_val
            info["probe_failed"] = ok
            if ok:
                non_monotone.append(name)
                best, best_id = cand, c.scenario_id  # closer failure: adopt it, say why
                info["to"] = probe_val
        refined[name] = info

    d_min = domain.distance(best)
    if d_min > base_fields["initial_distance"] + 1e-12:  # cannot happen by construction
        raise RuntimeError("minimizer produced a farther scenario")
    return MinimizationResult(
        status="minimized",
        minimized_values=best,
        minimized_distance=d_min,
        kept_variables=kept,
        candidates=ledger.candidates,
        episodes_used=ledger.episodes_used,
        exec_errors=ledger.exec_errors,
        **{
            **base_fields,
            "removed_variables": removed,
            "non_monotone_variables": non_monotone,
            "refined": refined,
        },
    )
