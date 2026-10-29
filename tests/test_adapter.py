"""The adapter boundary must refuse perturbations it cannot apply. The MuJoCo adapter
calls the same base-class check, so this is the only place it is tested."""

from __future__ import annotations

import pytest

from skuld.core.schemas import (
    Action,
    Observation,
    PerturbationDomain,
    Scenario,
    Trajectory,
    TrajectoryStep,
    VariableSpec,
)
from skuld.sim.adapter import SimulatorAdapter, UnsupportedPerturbationError

DOMAIN = PerturbationDomain(
    domain_id="push-v1",
    variables=[
        VariableSpec(name="object_mass_kg", unit="kg", nominal=0.1, min=0.05, max=0.5),
        VariableSpec(name="friction_coefficient", unit="1", nominal=0.6, min=0.2, max=1.0),
    ],
)


class MassOnlyAdapter(SimulatorAdapter):
    """A stand-in that can only change object mass."""

    sim_name = "fake"
    sim_version = "0"

    @property
    def supported_variables(self) -> frozenset[str]:
        return frozenset({"object_mass_kg"})

    def reset(self, scenario: Scenario, domain: PerturbationDomain) -> Observation:
        self.check_scenario(scenario, domain)
        return Observation(step=0, sim_time_s=0.0, source_sim_time_s=0.0, values=[0.0])

    def observe(self) -> Observation:  # pragma: no cover - not exercised here
        raise NotImplementedError

    def act(self, action: Action) -> None:  # pragma: no cover
        raise NotImplementedError

    def step(self) -> TrajectoryStep:  # pragma: no cover
        raise NotImplementedError

    def terminate(self) -> None:  # pragma: no cover
        return None

    def save_trajectory(self) -> Trajectory:  # pragma: no cover
        raise NotImplementedError


def test_adapter_boundary_refuses_wrong_domain_and_unsupported_variables() -> None:
    with pytest.raises(TypeError):
        SimulatorAdapter()  # type: ignore[abstract]
    adapter = MassOnlyAdapter()
    nominal = DOMAIN.nominal_values()
    wrong_domain = Scenario(scenario_id="wd", domain_ref="other-domain", values=nominal, seed=3)
    with pytest.raises(ValueError, match="references domain"):
        adapter.reset(wrong_domain, DOMAIN)
    low_friction = Scenario(
        scenario_id="lf",
        domain_ref="push-v1",
        values={"object_mass_kg": 0.1, "friction_coefficient": 0.3},
        seed=3,
    )
    with pytest.raises(UnsupportedPerturbationError, match="friction_coefficient"):
        adapter.reset(low_friction, DOMAIN)
