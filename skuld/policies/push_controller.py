"""Classical push controller: damped-least-squares differential IK on a nominal
kinematic model, with a small phase machine driven by the observation.

This is a *classical* policy (PolicyManifest.kind = classical). It knows the
robot's nominal kinematics (it loads the same staged scene the adapter uses) but
nothing about the perturbed world: mass, friction and observation delay are
hidden from it, which is the point of the test.

Every call to `act` recomputes the action from the current observation; nothing
is pre-recorded (runbook G05 step 55).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import mujoco
import numpy as np

from skuld.core import observation_layout as L
from skuld.core.schemas import Action, Observation, PolicyKind, PolicyManifest
from skuld.sim import scene as S

POLICY_ID = "push-dls-ik-v1"


class Phase(StrEnum):
    APPROACH_HIGH = "approach_high"
    DESCEND = "descend"
    PUSH = "push"
    HOLD = "hold"


class PushController:
    def __init__(
        self,
        scene_xml: str | Path,
        *,
        control_hz: float = 50.0,
        kp: float = 3.0,
        v_max_approach_mps: float = 0.25,
        v_max_push_mps: float = 0.12,
        dls_damping: float = 0.05,
        null_gain: float = 0.3,
        z_high_m: float = 0.12,
        z_push_m: float = 0.025,
        pre_offset_m: float = 0.07,
        push_offset_m: float = 0.0,
        stop_radius_m: float = 0.015,
        max_lead_rad: float = 0.15,
        kr: float = 4.0,
        w_max_radps: float = 1.5,
    ) -> None:
        self.control_hz = control_hz
        self.dt = 1.0 / control_hz
        self.kp = kp
        self.v_max_approach = v_max_approach_mps
        self.v_max_push = v_max_push_mps
        self.damping = dls_damping
        self.null_gain = null_gain
        self.z_high = z_high_m
        self.z_push = z_push_m
        self.pre_offset = pre_offset_m
        self.push_offset = push_offset_m
        self.stop_radius = stop_radius_m
        self.max_lead = max_lead_rad
        self.kr = kr
        self.w_max = w_max_radps

        # nominal kinematic model, used only for forward kinematics and Jacobians
        self._m = mujoco.MjModel.from_xml_path(str(scene_xml))
        self._d = mujoco.MjData(self._m)
        obj = mujoco.mjtObj
        self._ee_site = mujoco.mj_name2id(self._m, obj.mjOBJ_SITE, S.EE_SITE)
        arm_joints = [mujoco.mj_name2id(self._m, obj.mjOBJ_JOINT, n) for n in S.ARM_JOINTS]
        self._arm_qpos = np.array([self._m.jnt_qposadr[j] for j in arm_joints])
        self._arm_dof = np.array([self._m.jnt_dofadr[j] for j in arm_joints])
        arm_acts = [mujoco.mj_name2id(self._m, obj.mjOBJ_ACTUATOR, n) for n in S.ARM_ACTUATORS]
        self._arm_act = np.array(arm_acts)
        self._grip_act = mujoco.mj_name2id(self._m, obj.mjOBJ_ACTUATOR, S.GRIPPER_ACTUATOR)
        self._ctrl_lo = self._m.actuator_ctrlrange[self._arm_act, 0]
        self._ctrl_hi = self._m.actuator_ctrlrange[self._arm_act, 1]
        self._q_home = np.array(S.HOME_CTRL_ARM)
        self._jacp = np.zeros((3, self._m.nv))
        self._jacr = np.zeros((3, self._m.nv))
        # hold the hand at its home orientation (fingers pointing straight down)
        self._d.qpos[self._arm_qpos] = np.array(S.HOME_QPOS_ARM[:7])
        mujoco.mj_kinematics(self._m, self._d)
        self._quat_des = np.zeros(4)
        mujoco.mju_mat2Quat(self._quat_des, self._d.site_xmat[self._ee_site])
        self.reset()

    # ---------------------------------------------------------------- policy

    def reset(self) -> None:
        self.phase = Phase.APPROACH_HIGH
        # Commanded joint position is controller state. It is integrated from the
        # previous command, not from the measured angles, so the position actuators'
        # steady-state sag under gravity cannot swallow the velocity increment.
        self._q_cmd: np.ndarray | None = None

    def act(self, obs: Observation) -> Action:
        v = np.asarray(obs.values, dtype=float)
        ee = v[L.EE_POS]
        block = v[L.BLOCK_POS]
        target = v[L.TARGET_POS]
        q = v[L.ARM_QPOS]

        if self._q_cmd is None:
            self._q_cmd = q.copy()
        goal, v_max = self._choose_goal(ee, block, target)
        if self.phase is Phase.HOLD:
            q_des = self._q_cmd
        else:
            q_des = self._ik_step(q, ee, goal, v_max)
        # anti-windup: never command more than max_lead_rad ahead of the measured arm
        q_des = np.clip(q_des, q - self.max_lead, q + self.max_lead)
        q_des = np.clip(q_des, self._ctrl_lo, self._ctrl_hi)
        self._q_cmd = q_des

        ctrl = np.zeros(self._m.nu)
        ctrl[self._arm_act] = q_des
        ctrl[self._grip_act] = S.GRIPPER_CTRL_CLOSED
        return Action(step=obs.step, sim_time_s=obs.sim_time_s, values=[float(x) for x in ctrl])

    def manifest(self) -> PolicyManifest:
        src = Path(__file__).read_bytes()
        return PolicyManifest(
            policy_id=POLICY_ID,
            kind=PolicyKind.CLASSICAL,
            description=(
                "Damped-least-squares differential IK push controller with a four-phase "
                "approach/descend/push/hold machine; nominal kinematics, no learning."
            ),
            control_hz=self.control_hz,
            source_sha256=hashlib.sha256(src).hexdigest(),
            created_at=datetime.now(UTC),
        )

    # -------------------------------------------------------------- internals

    def _choose_goal(
        self, ee: np.ndarray, block: np.ndarray, target: np.ndarray
    ) -> tuple[np.ndarray, float]:
        to_target = target[:2] - block[:2]
        dist = float(np.linalg.norm(to_target))
        d = to_target / dist if dist > 1e-6 else np.array([0.0, 1.0])
        pre_xy = block[:2] - d * self.pre_offset
        ee_xy = ee[:2]
        ahead = float(np.dot(ee_xy - block[:2], d))  # >0 means ee is past the block
        rel = ee_xy - block[:2]
        lateral = float(abs(d[0] * rel[1] - d[1] * rel[0]))

        if dist < self.stop_radius:
            self.phase = Phase.HOLD

        if self.phase is Phase.APPROACH_HIGH:
            goal = np.array([pre_xy[0], pre_xy[1], self.z_high])
            if np.linalg.norm(ee_xy - pre_xy) < 0.015 and abs(ee[2] - self.z_high) < 0.02:
                self.phase = Phase.DESCEND
            return goal, self.v_max_approach

        if self.phase is Phase.DESCEND:
            goal = np.array([pre_xy[0], pre_xy[1], self.z_push])
            if abs(ee[2] - self.z_push) < 0.008 and np.linalg.norm(ee_xy - pre_xy) < 0.02:
                self.phase = Phase.PUSH
            return goal, self.v_max_approach

        if self.phase is Phase.PUSH:
            if ahead > 0.0 or lateral > 0.05:
                # lost the block: back off and re-approach
                self.phase = Phase.APPROACH_HIGH
                goal = np.array([pre_xy[0], pre_xy[1], self.z_high])
                return goal, self.v_max_approach
            # aim at (or just behind) the block centre: contact stops the fingers at the
            # face and the remaining position error becomes the push
            contact_xy = block[:2] - d * self.push_offset
            goal = np.array([contact_xy[0], contact_xy[1], self.z_push])
            return goal, self.v_max_push

        return ee.copy(), 0.0  # HOLD

    def _ik_step(
        self, q: np.ndarray, ee_observed: np.ndarray, goal: np.ndarray, v_max: float
    ) -> np.ndarray:
        m, d = self._m, self._d
        d.qpos[self._arm_qpos] = q
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)
        # closed loop on the *observed* end-effector position (which may be delayed);
        # the nominal model supplies the Jacobian and hand orientation at the measured q
        err = goal - ee_observed
        v = self.kp * err
        speed = float(np.linalg.norm(v))
        if speed > v_max > 0:
            v *= v_max / speed
        elif v_max <= 0:
            v[:] = 0.0

        rot = d.site_xmat[self._ee_site].reshape(3, 3)
        quat_cur = np.zeros(4)
        mujoco.mju_mat2Quat(quat_cur, d.site_xmat[self._ee_site])
        rot_err_local = np.zeros(3)
        mujoco.mju_subQuat(rot_err_local, self._quat_des, quat_cur)
        w = self.kr * (rot @ rot_err_local)  # world-frame angular velocity command
        wn = float(np.linalg.norm(w))
        if wn > self.w_max:
            w *= self.w_max / wn

        mujoco.mj_jacSite(m, d, self._jacp, self._jacr, self._ee_site)
        J = np.vstack([self._jacp[:, self._arm_dof], self._jacr[:, self._arm_dof]])  # 6 x 7
        twist = np.concatenate([v, w])
        JJt = J @ J.T + (self.damping**2) * np.eye(6)
        dq = J.T @ np.linalg.solve(JJt, twist)
        # null-space posture term biases the elbow toward the home configuration
        J_pinv = J.T @ np.linalg.inv(JJt)
        assert self._q_cmd is not None
        null = (np.eye(7) - J_pinv @ J) @ (self.null_gain * (self._q_home - self._q_cmd))
        return self._q_cmd + (dq + null) * self.dt
