"""MuJoCo adapter for the Panda push task (runbook G05, spec 12).

Perturbations are applied to the compiled model before the first step, so they
change the physics the policy is subjected to:

- object_offset_m      -> block start x (qpos of the free joint)
- object_mass_kg       -> block body mass and inertia, then mj_setConst
- friction_coefficient -> sliding friction of both block and floor geoms
- observation_delay_ms -> age of the observation returned by observe()

Every control step records qpos, qvel, block and end-effector positions, the
applied control and all contacts (body pair + normal force) so the oracle can
judge from telemetry rather than from pixels.
"""

from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import mujoco
import numpy as np

from skuld.core import observation_layout as L
from skuld.core.schemas import (
    Action,
    Contact,
    Observation,
    PerturbationDomain,
    Scenario,
    Trajectory,
    TrajectoryStep,
)
from skuld.sim import scene as S
from skuld.sim.adapter import SimulatorAdapter, UnsupportedPerturbationError

SUPPORTED = frozenset(
    {"object_offset_m", "object_mass_kg", "friction_coefficient", "observation_delay_ms"}
)


class MuJoCoPushAdapter(SimulatorAdapter):
    sim_name = "mujoco"
    sim_version = mujoco.__version__

    def __init__(
        self,
        menagerie_dir: str | Path,
        *,
        control_hz: float = 50.0,
        render: bool = False,
        width: int = 640,
        height: int = 480,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.staged = S.stage_scene(menagerie_dir, cache_dir)
        self.control_hz = float(control_hz)
        self._render = render
        self._width, self._height = width, height
        self._renderer: mujoco.Renderer | None = None
        self.model: mujoco.MjModel | None = None
        self.data: mujoco.MjData | None = None
        self._scenario: Scenario | None = None
        self._policy_ref = "unset"
        self._pending_ctrl: np.ndarray | None = None
        self._steps: list[TrajectoryStep] = []
        self._obs_buffer: deque[tuple[float, list[float]]] = deque()
        self._delay_s = 0.0
        self._step_index = 0

    # ---------------------------------------------------------------- contract

    @property
    def supported_variables(self) -> frozenset[str]:
        return SUPPORTED

    def set_policy_ref(self, policy_ref: str) -> None:
        self._policy_ref = policy_ref

    def reset(self, scenario: Scenario, domain: PerturbationDomain) -> Observation:
        self.check_scenario(scenario, domain)
        self._scenario = scenario
        values = dict(domain.nominal_values())
        values.update(scenario.values)

        model = mujoco.MjModel.from_xml_path(str(self.staged.scene_xml))
        data = mujoco.MjData(model)
        self.model, self.data = model, data
        self._ids()

        # --- perturbations on the compiled model ---------------------------
        mass = float(values.get("object_mass_kg", S.NOMINAL_BLOCK_MASS_KG))
        old_mass = float(model.body_mass[self._block_body])
        if old_mass <= 0:
            raise RuntimeError("block body has non-positive mass in the staged scene")
        model.body_mass[self._block_body] = mass
        model.body_inertia[self._block_body] *= mass / old_mass

        mu = float(values.get("friction_coefficient", S.NOMINAL_FRICTION))
        model.geom_friction[self._block_geom, 0] = mu
        model.geom_friction[self._floor_geom, 0] = mu

        mujoco.mj_setConst(model, data)

        self._delay_s = float(values.get("observation_delay_ms", 0.0)) / 1000.0

        # --- initial state -------------------------------------------------
        mujoco.mj_resetDataKeyframe(model, data, self._key)
        offset = float(values.get("object_offset_m", 0.0))
        data.qpos[self._block_qpos] += offset
        data.ctrl[:] = model.key_ctrl[self._key]
        data.ctrl[self._grip_act] = S.GRIPPER_CTRL_CLOSED  # closed fingers act as a pusher
        mujoco.mj_forward(model, data)

        self._n_sub = max(1, int(round(1.0 / (self.control_hz * model.opt.timestep))))
        self._pending_ctrl = data.ctrl.copy()
        self._steps = []
        self._step_index = 0
        self._obs_buffer.clear()
        self._obs_buffer.append((float(data.time), self._raw_obs()))
        if self._render:
            self._renderer = mujoco.Renderer(model, height=self._height, width=self._width)
        return self.observe()

    def observe(self) -> Observation:
        assert self.data is not None
        now = float(self.data.time)
        want = now - self._delay_s
        chosen_t, chosen = self._obs_buffer[0]
        for t, vals in self._obs_buffer:
            if t <= want + 1e-9:
                chosen_t, chosen = t, vals
            else:
                break
        # prune entries older than needed
        while len(self._obs_buffer) > 1 and self._obs_buffer[1][0] <= want + 1e-9:
            self._obs_buffer.popleft()
        return Observation(
            step=self._step_index,
            sim_time_s=now,
            source_sim_time_s=chosen_t,
            delay_applied_ms=(now - chosen_t) * 1000.0,
            values=list(chosen),
        )

    def act(self, action: Action) -> None:
        assert self.model is not None
        ctrl = np.asarray(action.values, dtype=float)
        if ctrl.shape != (self.model.nu,):
            raise ValueError(f"action has {ctrl.shape[0]} values, model has nu={self.model.nu}")
        lo, hi = self.model.actuator_ctrlrange[:, 0], self.model.actuator_ctrlrange[:, 1]
        self._pending_ctrl = np.clip(ctrl, lo, hi)

    def step(self) -> TrajectoryStep:
        assert self.model is not None and self.data is not None
        m, d = self.model, self.data
        d.ctrl[:] = self._pending_ctrl
        for _ in range(self._n_sub):
            mujoco.mj_step(m, d)
        self._step_index += 1
        self._obs_buffer.append((float(d.time), self._raw_obs()))
        step = TrajectoryStep(
            step=self._step_index - 1,
            sim_time_s=float(d.time),
            qpos=[float(x) for x in d.qpos],
            qvel=[float(x) for x in d.qvel],
            object_pos_m=tuple(float(x) for x in self.block_pos),
            ee_pos_m=tuple(float(x) for x in self.ee_pos),
            action=[float(x) for x in self._pending_ctrl],
            contacts=self._contacts(),
            observation_delay_ms=self._delay_s * 1000.0,
        )
        self._steps.append(step)
        return step

    def terminate(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    def save_trajectory(self) -> Trajectory:
        assert self.model is not None and self._scenario is not None
        return Trajectory(
            trajectory_id=f"traj-{self._scenario.scenario_id}-s{self._scenario.seed}",
            scenario_ref=self._scenario.scenario_id,
            policy_ref=self._policy_ref,
            sim_name=self.sim_name,
            sim_version=self.sim_version,
            scene_sha256=self.staged.scene_sha256,
            dt_s=1.0 / self.control_hz,
            steps=list(self._steps),
        )

    # ------------------------------------------------------------- telemetry

    @property
    def sim_time(self) -> float:
        assert self.data is not None
        return float(self.data.time)

    @property
    def block_pos(self) -> np.ndarray:
        assert self.data is not None
        return self.data.xpos[self._block_body].copy()

    @property
    def block_vel(self) -> np.ndarray:
        """Linear velocity of the block's free joint, world frame, m/s."""
        assert self.data is not None
        return self.data.qvel[self._block_dof : self._block_dof + 3].copy()

    @property
    def ee_pos(self) -> np.ndarray:
        assert self.data is not None
        return self.data.site_xpos[self._ee_site].copy()

    @property
    def target_pos(self) -> np.ndarray:
        assert self.data is not None
        return self.data.site_xpos[self._target_site].copy()

    @property
    def nu(self) -> int:
        assert self.model is not None
        return int(self.model.nu)

    def render_frame(self) -> np.ndarray:
        if self._renderer is None:
            raise RuntimeError("adapter was created with render=False")
        self._renderer.update_scene(self.data, camera=S.CAMERA)
        return self._renderer.render()

    def robot_collision_pairs(self, contacts: list[Contact]) -> list[Contact]:
        """Contacts the push spec forbids: arm links against anything, fingers against floor."""
        bad: list[Contact] = []
        for c in contacts:
            a, b = c.geom_a.split("/")[0], c.geom_b.split("/")[0]
            links = {a, b} & S.ROBOT_LINK_BODIES
            if links:
                bad.append(c)
                continue
            if ({a, b} & S.FINGER_BODIES) and (S.WORLD_BODY in {a, b}):
                bad.append(c)
        return bad

    # --------------------------------------------------------------- internals

    def _ids(self) -> None:
        m = self.model
        assert m is not None
        name2id = mujoco.mj_name2id
        obj = mujoco.mjtObj
        self._block_body = name2id(m, obj.mjOBJ_BODY, S.BLOCK_BODY)
        self._block_geom = name2id(m, obj.mjOBJ_GEOM, S.BLOCK_GEOM)
        self._floor_geom = name2id(m, obj.mjOBJ_GEOM, S.FLOOR_GEOM)
        self._ee_site = name2id(m, obj.mjOBJ_SITE, S.EE_SITE)
        self._target_site = name2id(m, obj.mjOBJ_SITE, S.TARGET_SITE)
        self._key = name2id(m, obj.mjOBJ_KEY, S.KEYFRAME)
        self._grip_act = name2id(m, obj.mjOBJ_ACTUATOR, S.GRIPPER_ACTUATOR)
        block_joint = name2id(m, obj.mjOBJ_JOINT, S.BLOCK_JOINT)
        self._block_qpos = int(m.jnt_qposadr[block_joint])
        self._block_dof = int(m.jnt_dofadr[block_joint])
        arm_joints = [name2id(m, obj.mjOBJ_JOINT, n) for n in S.ARM_JOINTS]
        self._arm_qpos = np.array([m.jnt_qposadr[j] for j in arm_joints])
        self._arm_dof = np.array([m.jnt_dofadr[j] for j in arm_joints])
        for ident, label in (
            (self._block_body, S.BLOCK_BODY),
            (self._block_geom, S.BLOCK_GEOM),
            (self._floor_geom, S.FLOOR_GEOM),
            (self._ee_site, S.EE_SITE),
            (self._target_site, S.TARGET_SITE),
            (self._key, S.KEYFRAME),
            (self._grip_act, S.GRIPPER_ACTUATOR),
            (block_joint, S.BLOCK_JOINT),
        ):
            if ident < 0:
                raise RuntimeError(f"staged scene is missing {label!r}")

    def _raw_obs(self) -> list[float]:
        d = self.data
        assert d is not None
        vals = np.empty(L.OBS_DIM)
        vals[L.EE_POS] = d.site_xpos[self._ee_site]
        vals[L.BLOCK_POS] = d.xpos[self._block_body]
        vals[L.TARGET_POS] = d.site_xpos[self._target_site]
        vals[L.ARM_QPOS] = d.qpos[self._arm_qpos]
        vals[L.ARM_QVEL] = d.qvel[self._arm_dof]
        if not np.all(np.isfinite(vals)):
            raise FloatingPointError("non-finite simulator state")
        return [float(x) for x in vals]

    def _contacts(self) -> list[Contact]:
        m, d = self.model, self.data
        assert m is not None and d is not None
        out: list[Contact] = []
        force = np.zeros(6)
        for i in range(d.ncon):
            c = d.contact[i]
            mujoco.mj_contactForce(m, d, i, force)
            out.append(
                Contact(
                    geom_a=self._geom_label(c.geom1),
                    geom_b=self._geom_label(c.geom2),
                    normal_force_n=float(abs(force[0])) if math.isfinite(force[0]) else None,
                )
            )
        return out

    def _geom_label(self, geom_id: int) -> str:
        m = self.model
        assert m is not None
        body = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[geom_id]))
        geom = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, geom_id) or str(geom_id)
        return f"{body}/{geom}"


__all__ = ["MuJoCoPushAdapter", "SUPPORTED", "UnsupportedPerturbationError"]
