"""Run one closed-loop episode: observe -> act -> step, with telemetry and video.

The goal check here is a *provisional* convenience for G05 so a run can be
labelled on the spot. The authoritative verdict comes from the deterministic
oracle (G06) applied to the saved Trajectory against an approved TestSpec.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from skuld.core.schemas import Action, Observation, PerturbationDomain, Scenario, Trajectory
from skuld.sim import scene as S
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter
from skuld.sim.video import FfmpegWriter


class Policy(Protocol):
    def reset(self) -> None: ...
    def act(self, obs: Observation) -> Action: ...


@dataclass
class EpisodeRun:
    trajectory: Trajectory
    steps: int
    sim_time_s: float
    reached_goal: bool
    time_to_goal_s: float | None
    final_block_to_target_m: float
    min_block_to_target_m: float
    robot_collision_steps: int
    block_toppled: bool
    video_path: str | None
    video_frames: int

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("trajectory")
        d["trajectory_id"] = self.trajectory.trajectory_id
        d["scene_sha256"] = self.trajectory.scene_sha256
        return d


def run_episode(
    adapter: MuJoCoPushAdapter,
    policy: Policy,
    scenario: Scenario,
    domain: PerturbationDomain,
    *,
    policy_ref: str,
    max_time_s: float = 15.0,
    goal_radius_m: float = S.TARGET_RADIUS_M,
    hold_steps: int = 25,
    settle_time_after_goal_s: float = 0.5,
    video_path: str | Path | None = None,
    fps: int = 25,
) -> EpisodeRun:
    adapter.set_policy_ref(policy_ref)
    obs = adapter.reset(scenario, domain)
    policy.reset()

    writer: FfmpegWriter | None = None
    frame_every = 1
    if video_path is not None:
        frame = adapter.render_frame()
        writer = FfmpegWriter(video_path, frame.shape[1], frame.shape[0], fps=fps)
        writer.write(frame)
        frame_every = max(1, int(round(adapter.control_hz / fps)))

    target = adapter.target_pos
    in_goal_run = 0
    reached = False
    time_to_goal: float | None = None
    min_dist = float("inf")
    collision_steps = 0
    toppled = False
    settle_until: float | None = None

    try:
        while adapter.sim_time < max_time_s:
            action = policy.act(obs)
            adapter.act(action)
            step = adapter.step()
            obs = adapter.observe()

            block = np.asarray(step.object_pos_m)
            dist = float(np.linalg.norm(block[:2] - target[:2]))
            min_dist = min(min_dist, dist)
            if adapter.robot_collision_pairs(step.contacts):
                collision_steps += 1
            if block[2] < S.BLOCK_HALF_M * 0.5:
                toppled = True  # centre dropped below half height: fell or clipped
            if dist <= goal_radius_m:
                in_goal_run += 1
                if in_goal_run >= hold_steps and not reached:
                    reached = True
                    time_to_goal = step.sim_time_s
                    settle_until = step.sim_time_s + settle_time_after_goal_s
            else:
                in_goal_run = 0

            if writer is not None and step.step % frame_every == 0:
                writer.write(adapter.render_frame())
            if settle_until is not None and step.sim_time_s >= settle_until:
                break
    finally:
        frames = writer.close() if writer is not None else 0
        adapter.terminate()

    traj = adapter.save_trajectory()
    final_dist = float(np.linalg.norm(np.asarray(traj.steps[-1].object_pos_m)[:2] - target[:2]))
    return EpisodeRun(
        trajectory=traj,
        steps=len(traj.steps),
        sim_time_s=traj.steps[-1].sim_time_s,
        reached_goal=reached,
        time_to_goal_s=time_to_goal,
        final_block_to_target_m=final_dist,
        min_block_to_target_m=min_dist,
        robot_collision_steps=collision_steps,
        block_toppled=toppled,
        video_path=str(video_path) if video_path is not None else None,
        video_frames=frames,
    )
