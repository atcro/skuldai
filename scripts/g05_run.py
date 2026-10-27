"""G05 evidence run: nominal episode with video, exact replay, and a handful of
extreme-but-in-domain scenarios to see whether anything breaks the policy.

Reports what actually happened. A scenario that does not fail is reported as a
pass; no number here is a claim beyond "this ran, under this simulator".

Usage: MUJOCO_GL=egl python scripts/g05_run.py --menagerie <dir> --out evidence/G05
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from skuld.core.domains import PUSH_V1
from skuld.core.schemas import Scenario
from skuld.policies.push_controller import POLICY_ID, PushController
from skuld.sim.episode import run_episode
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

CANDIDATES: dict[str, dict[str, float]] = {
    "heavy": {"object_mass_kg": 0.5},
    "slippery": {"friction_coefficient": 0.2},
    "sticky": {"friction_coefficient": 1.0},
    "offset_pos": {"object_offset_m": 0.10},
    "offset_neg": {"object_offset_m": -0.10},
    "delay_100": {"observation_delay_ms": 100.0},
    "delay_200": {"observation_delay_ms": 200.0},
    "combo": {"friction_coefficient": 0.2, "observation_delay_ms": 200.0, "object_offset_m": 0.10},
}


def scenario(name: str, overrides: dict[str, float], seed: int) -> Scenario:
    values = PUSH_V1.nominal_values()
    values.update(overrides)
    return Scenario(scenario_id=name, domain_ref=PUSH_V1.domain_id, values=values, seed=seed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--menagerie", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-time", type=float, default=15.0)
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    adapter = MuJoCoPushAdapter(args.menagerie, render=not args.no_video)
    policy = PushController(adapter.staged.scene_xml)
    manifest = policy.manifest()
    (out / "policy_manifest.json").write_text(manifest.model_dump_json(indent=2))
    (out / "domain_push_v1.json").write_text(PUSH_V1.model_dump_json(indent=2))
    (out / "scene_sha256.txt").write_text(adapter.staged.scene_sha256 + "\n")

    report: dict = {
        "gate": "G05",
        "policy_id": POLICY_ID,
        "policy_source_sha256": manifest.source_sha256,
        "scene_sha256": adapter.staged.scene_sha256,
        "sim": f"{adapter.sim_name} {adapter.sim_version}",
        "control_hz": adapter.control_hz,
        "max_time_s": args.max_time,
        "episodes": {},
    }

    def run(name: str, sc: Scenario, video: bool) -> dict:
        t0 = time.perf_counter()
        ep = run_episode(
            adapter,
            policy,
            sc,
            PUSH_V1,
            policy_ref=POLICY_ID,
            max_time_s=args.max_time,
            video_path=(out / f"{name}.mp4") if (video and not args.no_video) else None,
        )
        wall = time.perf_counter() - t0
        (out / f"{name}.trajectory.json").write_text(ep.trajectory.model_dump_json())
        summary = ep.summary()
        summary.update(
            scenario=sc.model_dump(mode="json"),
            distance_from_nominal=sc.distance_from_nominal(PUSH_V1),
            wallclock_s=wall,
            realtime_factor=ep.sim_time_s / wall if wall > 0 else None,
        )
        print(
            f"{name:12s} goal={ep.reached_goal!s:5s} t_goal={ep.time_to_goal_s} "
            f"final={ep.final_block_to_target_m:.3f}m min={ep.min_block_to_target_m:.3f}m "
            f"collisions={ep.robot_collision_steps} toppled={ep.block_toppled} "
            f"steps={ep.steps} wall={wall:.1f}s"
        )
        return summary

    # 1. nominal with video
    nominal = scenario("nominal", {}, seed=0)
    report["episodes"]["nominal"] = run("nominal", nominal, video=True)

    # 2. exact replay of the nominal scenario (same seed, same everything)
    replay = run("nominal_replay", nominal, video=False)
    a = json.loads((out / "nominal.trajectory.json").read_text())
    b = json.loads((out / "nominal_replay.trajectory.json").read_text())
    n = min(len(a["steps"]), len(b["steps"]))
    qa = np.array([s["qpos"] for s in a["steps"][:n]])
    qb = np.array([s["qpos"] for s in b["steps"][:n]])
    oa = np.array([s["object_pos_m"] for s in a["steps"][:n]])
    ob = np.array([s["object_pos_m"] for s in b["steps"][:n]])
    report["replay"] = {
        "steps_compared": n,
        "same_length": len(a["steps"]) == len(b["steps"]),
        "max_abs_qpos_diff": float(np.max(np.abs(qa - qb))),
        "max_abs_object_pos_diff": float(np.max(np.abs(oa - ob))),
        "bit_identical": bool(np.array_equal(qa, qb) and np.array_equal(oa, ob)),
    }
    report["episodes"]["nominal_replay"] = replay
    print("replay:", json.dumps(report["replay"]))

    # 3. extreme-but-in-domain candidates
    for name, overrides in CANDIDATES.items():
        sc = scenario(name, overrides, seed=0)
        report["episodes"][name] = run(name, sc, video=True)

    failures = [k for k, v in report["episodes"].items() if not v["reached_goal"]]
    report["observed_failures"] = failures
    report["note"] = (
        "Provisional goal check (block within target radius for 25 control steps). "
        "Authoritative verdicts come from the G06 oracle. Nothing here is a safety claim."
    )
    (out / "g05_run_report.json").write_text(json.dumps(report, indent=2))
    print("observed failures:", failures or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
