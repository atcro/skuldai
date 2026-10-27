"""G05 step 60: each perturbation must change simulator parameters or what the
policy observes. Runs only where MuJoCo and the pinned Menagerie checkout exist
(the simulator venv in WSL2); skipped in the app venv and in CI.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

MENAGERIE = os.environ.get("SKULD_MENAGERIE_DIR")
if not MENAGERIE or not (Path(MENAGERIE) / "franka_emika_panda" / "panda.xml").is_file():
    pytest.skip("SKULD_MENAGERIE_DIR not set or Panda model missing", allow_module_level=True)

from skuld.core import observation_layout as L  # noqa: E402
from skuld.core.domains import PUSH_V1  # noqa: E402
from skuld.core.schemas import Action, Scenario  # noqa: E402
from skuld.sim import scene as S  # noqa: E402
from skuld.sim.adapter import UnsupportedPerturbationError  # noqa: E402
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter  # noqa: E402


def make_scenario(name: str, **overrides: float) -> Scenario:
    values = PUSH_V1.nominal_values()
    values.update(overrides)
    return Scenario(scenario_id=name, domain_ref=PUSH_V1.domain_id, values=values, seed=0)


@pytest.fixture(scope="module")
def adapter(tmp_path_factory: pytest.TempPathFactory) -> MuJoCoPushAdapter:
    cache = tmp_path_factory.mktemp("scene")
    return MuJoCoPushAdapter(MENAGERIE, cache_dir=cache)


def test_scene_stages_and_hashes(adapter: MuJoCoPushAdapter) -> None:
    assert adapter.staged.scene_xml.is_file()
    assert len(adapter.staged.scene_sha256) == 64
    # staging is idempotent and the hash is stable
    again = S.stage_scene(MENAGERIE, adapter.staged.scene_xml.parent)
    assert again.scene_sha256 == adapter.staged.scene_sha256


def test_nominal_reset_matches_scene_constants(adapter: MuJoCoPushAdapter) -> None:
    obs = adapter.reset(make_scenario("nominal"), PUSH_V1)
    assert len(obs.values) == L.OBS_DIM
    block = np.array(obs.values[L.BLOCK_POS])
    assert block == pytest.approx(S.BLOCK_START_M, abs=1e-6)
    assert adapter.model.body_mass[adapter._block_body] == pytest.approx(S.NOMINAL_BLOCK_MASS_KG)
    assert adapter.model.geom_friction[adapter._block_geom, 0] == pytest.approx(S.NOMINAL_FRICTION)
    assert obs.delay_applied_ms == 0.0


def test_mass_perturbation_changes_model(adapter: MuJoCoPushAdapter) -> None:
    adapter.reset(make_scenario("heavy", object_mass_kg=0.5), PUSH_V1)
    assert adapter.model.body_mass[adapter._block_body] == pytest.approx(0.5)
    inertia_heavy = adapter.model.body_inertia[adapter._block_body].copy()
    adapter.reset(make_scenario("nominal"), PUSH_V1)
    inertia_nominal = adapter.model.body_inertia[adapter._block_body]
    assert np.all(inertia_heavy > inertia_nominal)


def test_friction_perturbation_changes_both_geoms(adapter: MuJoCoPushAdapter) -> None:
    adapter.reset(make_scenario("slippery", friction_coefficient=0.2), PUSH_V1)
    assert adapter.model.geom_friction[adapter._block_geom, 0] == pytest.approx(0.2)
    assert adapter.model.geom_friction[adapter._floor_geom, 0] == pytest.approx(0.2)


def test_offset_perturbation_moves_the_block(adapter: MuJoCoPushAdapter) -> None:
    obs = adapter.reset(make_scenario("offset", object_offset_m=0.08), PUSH_V1)
    block = np.array(obs.values[L.BLOCK_POS])
    assert block[0] == pytest.approx(S.BLOCK_START_M[0] + 0.08, abs=1e-6)
    assert block[1] == pytest.approx(S.BLOCK_START_M[1], abs=1e-6)


def test_delay_perturbation_makes_observations_stale(adapter: MuJoCoPushAdapter) -> None:
    adapter.reset(make_scenario("delayed", observation_delay_ms=100.0), PUSH_V1)
    hold = Action(step=0, sim_time_s=0.0, values=list(adapter.data.ctrl))
    for _ in range(10):  # 10 control steps = 200 ms at 50 Hz
        adapter.act(hold)
        adapter.step()
    obs = adapter.observe()
    assert obs.delay_applied_ms == pytest.approx(100.0, abs=1e-6)
    assert obs.source_sim_time_s == pytest.approx(obs.sim_time_s - 0.1, abs=1e-9)


def test_action_actually_moves_the_arm(adapter: MuJoCoPushAdapter) -> None:
    obs0 = adapter.reset(make_scenario("nominal"), PUSH_V1)
    q0 = np.array(obs0.values[L.ARM_QPOS])
    ctrl = np.array(adapter.data.ctrl)
    ctrl[0] = 1.0  # command joint 1 to 1 rad
    for _ in range(50):
        adapter.act(Action(step=0, sim_time_s=0.0, values=list(ctrl)))
        adapter.step()
    q1 = np.array(adapter.observe().values[L.ARM_QPOS])
    assert abs(q1[0] - q0[0]) > 0.3


def test_unsupported_variable_is_refused(adapter: MuJoCoPushAdapter) -> None:
    from skuld.core.schemas import PerturbationDomain, VariableSpec

    other = PerturbationDomain(
        domain_id="cam",
        variables=[VariableSpec(name="camera_yaw_deg", unit="deg", nominal=0, min=-10, max=10)],
    )
    sc = Scenario(scenario_id="c", domain_ref="cam", values={"camera_yaw_deg": 3.0}, seed=0)
    with pytest.raises(UnsupportedPerturbationError, match="camera_yaw_deg"):
        adapter.reset(sc, other)


def test_replay_is_bit_identical_for_fifty_steps(adapter: MuJoCoPushAdapter) -> None:
    def rollout() -> np.ndarray:
        adapter.reset(make_scenario("nominal"), PUSH_V1)
        ctrl = np.array(adapter.data.ctrl)
        ctrl[0] = 0.5
        traj = []
        for _ in range(50):
            adapter.act(Action(step=0, sim_time_s=0.0, values=list(ctrl)))
            traj.append(adapter.step().qpos)
        return np.array(traj)

    assert np.array_equal(rollout(), rollout())
