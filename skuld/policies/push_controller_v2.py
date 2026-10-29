"""Repair attempt: push controller v2 (classical, labelled as such).

Diagnosis from G10: the minimized counterexample is observation delay alone
(140 ms, everything else nominal) and the signature is a finger touching the
floor during descent. v1 closes the loop on the *observed* end-effector height
and descends at up to 0.25 m/s, so with a delay of `tau` it believes it is
`v * tau` higher than it is: 0.25 m/s x 0.14 s = 3.5 cm, more than the 2.5 cm
push height. The fingertip reaches the floor before the controller sees it.

The repair is the smallest explainable change that attacks that mechanism:

- below `z_slow_m` the vertical approach speed is capped at `v_z_slow_mps`
  (0.05 m/s: 1 cm of overshoot at 200 ms delay instead of 5 cm);
- the push height is raised from 2.5 cm to 3.0 cm (the block is 4 cm tall).

Nothing else changes. v1's source file is untouched so its hash, and every
stored result that cites it, stays valid. v2's identity hashes both files.
Whether this is an improvement is decided only by re-running the full suites
(nominal, stored regressions, held-out) through the oracle and the gate.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import mujoco
import numpy as np

from skuld.core.schemas import PolicyKind, PolicyManifest
from skuld.policies import push_controller as v1

POLICY_ID = "push-dls-ik-v2"


class PushControllerV2(v1.PushController):
    def __init__(
        self,
        scene_xml: str | Path,
        *,
        z_slow_m: float = 0.06,
        v_z_slow_mps: float = 0.05,
        z_push_m: float = 0.030,
        **kwargs,
    ) -> None:
        super().__init__(scene_xml, z_push_m=z_push_m, **kwargs)
        self.z_slow = z_slow_m
        self.v_z_slow = v_z_slow_mps

    def _ik_step(
        self, q: np.ndarray, ee_observed: np.ndarray, goal: np.ndarray, v_max: float
    ) -> np.ndarray:
        m, d = self._m, self._d
        d.qpos[self._arm_qpos] = q
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)
        err = goal - ee_observed
        v = self.kp * err
        speed = float(np.linalg.norm(v))
        if speed > v_max > 0:
            v *= v_max / speed
        elif v_max <= 0:
            v[:] = 0.0
        # --- the repair: slow vertical descent near the floor ---------------------
        if ee_observed[2] < self.z_slow and v[2] < -self.v_z_slow:
            v[2] = -self.v_z_slow

        rot = d.site_xmat[self._ee_site].reshape(3, 3)
        quat_cur = np.zeros(4)
        mujoco.mju_mat2Quat(quat_cur, d.site_xmat[self._ee_site])
        rot_err_local = np.zeros(3)
        mujoco.mju_subQuat(rot_err_local, self._quat_des, quat_cur)
        w = self.kr * (rot @ rot_err_local)
        wn = float(np.linalg.norm(w))
        if wn > self.w_max:
            w *= self.w_max / wn

        mujoco.mj_jacSite(m, d, self._jacp, self._jacr, self._ee_site)
        J = np.vstack([self._jacp[:, self._arm_dof], self._jacr[:, self._arm_dof]])
        twist = np.concatenate([v, w])
        JJt = J @ J.T + (self.damping**2) * np.eye(6)
        dq = J.T @ np.linalg.solve(JJt, twist)
        J_pinv = J.T @ np.linalg.inv(JJt)
        assert self._q_cmd is not None
        null = (np.eye(7) - J_pinv @ J) @ (self.null_gain * (self._q_home - self._q_cmd))
        return self._q_cmd + (dq + null) * self.dt

    def manifest(self) -> PolicyManifest:
        src = Path(v1.__file__).read_bytes() + Path(__file__).read_bytes()
        return PolicyManifest(
            policy_id=POLICY_ID,
            kind=PolicyKind.CLASSICAL,
            description=(
                "v1 damped-least-squares IK push controller plus a repair for the G10 "
                "counterexample: vertical speed capped at 0.05 m/s below 6 cm and push "
                "height 3.0 cm. Classical, no learning. Identity hashes v1 and v2 sources."
            ),
            control_hz=self.control_hz,
            source_sha256=hashlib.sha256(src).hexdigest(),
            created_at=datetime.now(UTC),
        )
