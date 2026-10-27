"""Test specifications for the push task.

A TestSpec is the only source of thresholds (spec 7.3). It is PROPOSED until a
human sets `approved_by` / `approved_at`; the oracle refuses unapproved specs
unless explicitly told the run is provisional.
"""

from __future__ import annotations

from datetime import UTC, datetime

from skuld.core.schemas import GoalCondition, SafetyRules, TestSpec
from skuld.sim import scene as S

#: Target centre in the horizontal plane, world frame, metres. Comes from the
#: staged scene, which is hashed into every trajectory's scene_sha256.
TARGET_XY_M: tuple[float, float] = (S.TARGET_POS_M[0], S.TARGET_POS_M[1])

PUSH_SPEC_V1 = TestSpec(
    spec_id="push-block",
    version=1,
    task=(
        "Franka Panda pushes a 4 cm cube from its start pose into a circular target region on "
        "the floor using closed fingertips, without touching the floor with the hand or fingers "
        "and without any arm link touching anything."
    ),
    goal=GoalCondition(
        description=(
            "Block centre within target_radius_m of the target centre in the horizontal plane "
            "for stability_steps consecutive control steps, the window completing no later than "
            "deadline_s after episode start, and the block still inside the target at the final "
            "recorded step."
        ),
        target_radius_m=S.TARGET_RADIUS_M,
        stability_steps=25,
    ),
    deadline_s=15.0,
    safety=SafetyRules(
        collision_forbidden=True,
        # end-effector must stay above the floor plane and within reach of the table area
        workspace_limits_m=(0.0, 0.9, -0.6, 0.6, -0.01, 0.8),
        # MuJoCo reports contact normal forces, but they are not calibrated against any
        # real gripper; no force limit is claimed for v1 (spec 7.3, 8.2).
        force_telemetry_available=False,
        force_limit_n=None,
    ),
)


def approve(spec: TestSpec, approved_by: str, at: datetime | None = None) -> TestSpec:
    """Return an approved copy. Only a human calls this; Claude never does (CLAUDE.md rule 7)."""
    return spec.model_copy(
        update={"approved_by": approved_by, "approved_at": at or datetime.now(UTC)}
    )


SPECS = {f"{PUSH_SPEC_V1.spec_id}-v{PUSH_SPEC_V1.version}": PUSH_SPEC_V1}
