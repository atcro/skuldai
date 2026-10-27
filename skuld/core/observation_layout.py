"""Fixed layout of the flat observation vector shared by adapter and policy.

The policy may only read what is in this vector. Perturbations that do not
change any of these values, or the dynamics that produce them, are meaningless
for this policy and must not be put in a domain (spec 7.1).
"""

from __future__ import annotations

N_ARM_JOINTS = 7

EE_POS = slice(0, 3)  # end-effector site position, world frame, metres
BLOCK_POS = slice(3, 6)  # block centre, world frame, metres
TARGET_POS = slice(6, 9)  # target centre, world frame, metres (constant per scene)
ARM_QPOS = slice(9, 9 + N_ARM_JOINTS)  # joint angles, rad
ARM_QVEL = slice(9 + N_ARM_JOINTS, 9 + 2 * N_ARM_JOINTS)  # joint velocities, rad/s

OBS_DIM = 9 + 2 * N_ARM_JOINTS  # 23
