"""G10: active search and minimizer against a synthetic objective (no simulator).

The synthetic failure region is "delay > 120 ms and mass > 0.25 kg"; offset and
friction are irrelevant. Everything here checks search *mechanics*: budget,
domain bounds, seeding, ledger completeness, revert/refine logic. Whether the
method beats random on the real simulator is an empirical question answered
only by evidence/G10.
"""

from __future__ import annotations

from skuld.core.domains import PUSH_V1
from skuld.core.schemas import Counterexample, EpisodeStatus, Scenario
from skuld.search import (
    ActiveSearchConfig,
    MinimizationConfig,
    Outcome,
    active_search,
    minimize_failure,
)
from skuld.search.plot import write_comparison_svg

D = PUSH_V1


def synthetic(values, scenario_id, seed):
    fail = values["observation_delay_ms"] > 120 and values["object_mass_kg"] > 0.25
    return Outcome(EpisodeStatus.SAFETY_FAIL if fail else EpisodeStatus.PASS, wallclock_s=0.01)


def test_active_search_is_seeded_bounded_and_fully_logged(tmp_path) -> None:
    cfg = ActiveSearchConfig(budget=25, sampler_seed=20261027)
    a = active_search(D, synthetic, cfg)
    b = active_search(D, synthetic, cfg)
    c = active_search(D, synthetic, cfg.model_copy(update={"sampler_seed": 1}))
    assert a.candidates == b.candidates and a.candidates != c.candidates
    assert a.metrics["episodes_used"] == 25 and len(a.candidates) == 25
    assert len(a.curve) == 25 and a.curve[-1].cumulative_episodes == 25
    for cand in a.candidates:
        D.check_values(cand.values)
    assert a.explore_episodes + a.contract_episodes == 25
    # the region covers 40% x 55% of the box, so exploration finds it and contraction improves on it
    first = next(x for x in a.candidates if x.valid_failure)
    assert a.best is not None and a.best.distance_from_nominal < first.distance_from_nominal
    assert a.best.valid_failure and a.incumbents[0] == first.scenario_id
    assert all(x.accepted for x in a.candidates if x.scenario_id in a.incumbents)
    assert {x.move for x in a.candidates} >= {"uniform", "contract"}

    # the hypothesis box restricts exploration; a box outside the domain is refused
    boxed = active_search(
        D,
        synthetic,
        cfg.model_copy(update={"explore_box": {"observation_delay_ms": (150.0, 200.0)}}),
    )
    assert all(
        150 <= x.values["observation_delay_ms"] <= 200
        for x in boxed.candidates
        if x.phase == "explore"
    )
    try:
        active_search(
            D, synthetic, cfg.model_copy(update={"explore_box": {"object_mass_kg": (0.0, 0.5)}})
        )
    except ValueError:
        pass
    else:
        raise AssertionError("box outside the domain was accepted")

    # EXEC_ERROR is logged but never counts against the budget
    calls = {"n": 0}

    def flaky(values, scenario_id, seed):
        calls["n"] += 1
        if calls["n"] == 2:
            return Outcome(EpisodeStatus.EXEC_ERROR)
        return synthetic(values, scenario_id, seed)

    f = active_search(D, flaky, ActiveSearchConfig(budget=10, sampler_seed=3))
    assert f.metrics["episodes_used"] == 10 and f.metrics["exec_errors_not_counted"] == 1
    assert len(f.candidates) == 11 and not f.candidates[1].counts_against_budget

    write_comparison_svg(
        tmp_path / "cmp.svg", {"random": c.curve, "active": a.curve}, budget=25, caption="t"
    )
    svg = (tmp_path / "cmp.svg").read_text()
    assert svg.count("<polyline") == 4 and "running min distance" in svg


def test_minimizer_reverts_irrelevant_variables_and_refines_the_rest() -> None:
    initial = {
        "object_offset_m": 0.08,
        "object_mass_kg": 0.45,
        "friction_coefficient": 0.9,
        "observation_delay_ms": 190.0,
    }
    r = minimize_failure(D, initial, synthetic, MinimizationConfig(seeds=[0, 1]))
    assert r.status == "minimized"
    assert set(r.removed_variables) == {"object_offset_m", "friction_coefficient"}
    assert r.kept_variables == ["object_mass_kg", "observation_delay_ms"]  # nearest first
    assert r.minimized_values["object_offset_m"] == 0.0
    assert r.minimized_values["friction_coefficient"] == 0.6
    # bisection moved both kept variables toward the true boundary without crossing it
    assert 0.25 < r.minimized_values["object_mass_kg"] < 0.45
    assert 120 < r.minimized_values["observation_delay_ms"] < 190
    assert r.minimized_distance < r.initial_distance
    assert r.non_monotone_variables == []
    assert r.candidates[0].phase == "confirm" and r.candidates[0].accepted
    # every seed was run for every candidate configuration
    assert r.episodes_used % 2 == 0 and r.episodes_used == len(r.candidates)
    ce = Counterexample(
        counterexample_id="t",
        original=Scenario(scenario_id="o", domain_ref=D.domain_id, values=initial, seed=0),
        minimized=Scenario(
            scenario_id="m", domain_ref=D.domain_id, values=r.minimized_values, seed=0
        ),
        removed_variables=r.removed_variables,
        kept_variables=r.kept_variables,
        replay_seeds=[0, 1],
        replay_runs=2,
        replay_failures=2,
    )
    ce.check_minimized(D)

    # a scenario that does not fail is refused, not "minimized"
    nominal = D.nominal_values()
    assert minimize_failure(D, nominal, synthetic).status == "not_reproduced"

    # non-monotone axis: a second failure band at delay 40..60 ms is found by the probe
    def banded(values, scenario_id, seed):
        if 40 <= values["observation_delay_ms"] <= 60 and values["object_mass_kg"] > 0.25:
            return Outcome(EpisodeStatus.TASK_FAIL)
        return synthetic(values, scenario_id, seed)

    nm = minimize_failure(D, initial, banded, MinimizationConfig(refine_steps=2))
    assert nm.non_monotone_variables == ["observation_delay_ms"]
    assert 40 <= nm.minimized_values["observation_delay_ms"] <= 60
    assert nm.minimized_distance < r.minimized_distance
