"""The adapter boundary must refuse perturbations it cannot apply."""

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


@pytest.fixture
def domain() -> PerturbationDomain:
    return PerturbationDomain(
        domain_id="push-v1",
        variables=[
            VariableSpec(name="object_mass_kg", unit="kg", nominal=0.1, min=0.05, max=0.5),
            VariableSpec(name="friction_coefficient", unit="1", nominal=0.6, min=0.2, max=1.0),
        ],
    )


def test_adapter_refuses_unsupported_variable(domain: PerturbationDomain) -> None:
    scenario = Scenario(
        scenario_id="low-friction",
        domain_ref=domain.domain_id,
        values={"object_mass_kg": 0.1, "friction_coefficient": 0.3},
        seed=3,
    )
    with pytest.raises(UnsupportedPerturbationError, match="friction_coefficient"):
        MassOnlyAdapter().reset(scenario, domain)


def test_adapter_checks_domain_before_support(domain: PerturbationDomain) -> None:
    scenario = Scenario(
        scenario_id="wrong-domain",
        domain_ref="other-domain",
        values={"object_mass_kg": 0.1, "friction_coefficient": 0.6},
        seed=3,
    )
    with pytest.raises(ValueError, match="references domain"):
        MassOnlyAdapter().reset(scenario, domain)


def test_abstract_adapter_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        SimulatorAdapter()  # type: ignore[abstract]
