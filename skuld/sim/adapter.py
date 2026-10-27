"""Simulator adapter contract (spec.md section 12, runbook G02 step 27).

An adapter owns one simulator instance. It must refuse any scenario variable it
cannot actually apply: a perturbation that silently does nothing would make every
downstream result meaningless (runbook audit, "only perturb variables actually
observed/used"). The MuJoCo adapter arrives in G05; this module is the boundary
the rest of Skuld codes against.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from skuld.core.schemas import (
    Action,
    Observation,
    PerturbationDomain,
    Scenario,
    Trajectory,
    TrajectoryStep,
)


class UnsupportedPerturbationError(ValueError):
    """Raised when a scenario varies something this adapter cannot apply."""


class SimulatorAdapter(ABC):
    """Lifecycle: reset -> (observe -> act -> step)* -> terminate -> save_trajectory."""

    #: Human-readable simulator identity, recorded in every trajectory.
    sim_name: str
    sim_version: str

    @property
    @abstractmethod
    def supported_variables(self) -> frozenset[str]:
        """Variable names this adapter can physically apply."""

    def check_scenario(self, scenario: Scenario, domain: PerturbationDomain) -> None:
        """Validate against the domain, then against what this adapter can do."""
        scenario.check_against(domain)
        unsupported = sorted(set(scenario.values) - self.supported_variables)
        if unsupported:
            raise UnsupportedPerturbationError(
                f"{self.sim_name} cannot apply {unsupported}; "
                f"supported: {sorted(self.supported_variables)}"
            )

    @abstractmethod
    def reset(self, scenario: Scenario, domain: PerturbationDomain) -> Observation:
        """Load the scene, apply every scenario value, seed RNGs, return the first observation.

        Implementations must call `check_scenario` first.
        """

    @abstractmethod
    def observe(self) -> Observation:
        """Current observation, with any configured delay already applied."""

    @abstractmethod
    def act(self, action: Action) -> None:
        """Set the control to apply on the next step."""

    @abstractmethod
    def step(self) -> TrajectoryStep:
        """Advance physics by one control period and return the recorded step."""

    @abstractmethod
    def terminate(self) -> None:
        """Release simulator resources. Idempotent."""

    @abstractmethod
    def save_trajectory(self) -> Trajectory:
        """Return the complete, validated trajectory since the last reset."""
