"""Perturbation domains. PROPOSED until frozen in G07 (spec 8.1 step 1).

Only variables the push policy actually observes or that actually change the
dynamics of the push task are listed. Camera and lighting are absent because the
controller reads simulator state, not pixels.
"""

from __future__ import annotations

from skuld.core.schemas import PerturbationDomain, VariableSpec

PUSH_V1 = PerturbationDomain(
    domain_id="push-v1",
    variables=[
        VariableSpec(
            # Lateral offset of the block's start position, perpendicular to the
            # nominal push direction (+y). Applied along world x.
            name="object_offset_m",
            unit="m",
            nominal=0.0,
            min=-0.10,
            max=0.10,
        ),
        VariableSpec(name="object_mass_kg", unit="kg", nominal=0.1, min=0.05, max=0.5),
        VariableSpec(
            # Sliding friction coefficient applied to both the block and the floor,
            # so it is the effective pair friction (MuJoCo takes the pairwise max).
            name="friction_coefficient",
            unit="1",
            nominal=0.6,
            min=0.2,
            max=1.0,
        ),
        VariableSpec(
            # Age of the observation the policy receives, from a history buffer
            # indexed by simulator time; quantised to the control period.
            name="observation_delay_ms",
            unit="ms",
            nominal=0.0,
            min=0.0,
            max=200.0,
        ),
    ],
)

DOMAINS = {PUSH_V1.domain_id: PUSH_V1}
