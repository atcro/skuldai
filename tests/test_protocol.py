"""G07: the locked protocol and its scenario sampler (no simulator needed)."""

from __future__ import annotations

import numpy as np

from skuld.core.domains import PUSH_V1
from skuld.core.protocol import PROTOCOL_V1, random_scenarios, sample_uniform
from skuld.oracle.specs import PUSH_SPEC_V1


def test_protocol_is_locked_consistent_and_hashable() -> None:
    p = PROTOCOL_V1
    assert p.spec_sha256 == PUSH_SPEC_V1.digest()
    assert PUSH_SPEC_V1.is_approved
    assert p.domain.domain_id == PUSH_V1.domain_id
    assert len(p.held_out_configs) == len(p.seeds.held_out)
    assert {s.seed for s in p.held_out_configs} == set(p.seeds.held_out)
    assert set(p.seeds.nominal).isdisjoint(p.seeds.held_out)
    for s in p.held_out_configs:
        s.check_against(p.domain)
    # the lock is reproducible: building the same protocol twice yields the same digest
    again = random_scenarios(
        PUSH_V1,
        5,
        sampler_seed=p.sampler_seeds.held_out_configs,
        prefix="heldout",
        first_seed=p.seeds.held_out[0],
    )
    assert again == p.held_out_configs
    assert len(p.digest()) == 64


def test_sampler_is_in_bounds_and_seeded() -> None:
    a = random_scenarios(PUSH_V1, 50, sampler_seed=7, prefix="x", first_seed=0)
    b = random_scenarios(PUSH_V1, 50, sampler_seed=7, prefix="x", first_seed=0)
    c = random_scenarios(PUSH_V1, 50, sampler_seed=8, prefix="x", first_seed=0)
    assert a == b and a != c
    for s in a:
        PUSH_V1.check_values(s.values)  # within [min, max], all names present
    # every variable actually varies across the sample
    for v in PUSH_V1.variables:
        vals = [s.values[v.name] for s in a]
        assert max(vals) - min(vals) > 0.5 * v.range
    one = sample_uniform(PUSH_V1, np.random.default_rng(0))
    assert set(one) == PUSH_V1.names
