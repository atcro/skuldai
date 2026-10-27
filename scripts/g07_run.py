"""G07 evidence run: nominal runs, uniform-random baseline, spot-check replays,
one video of the first random failure (if any). Every episode is stored
(gzipped trajectory + oracle EpisodeResult) and hashed into a manifest.

Usage (sim venv):
  MUJOCO_GL=egl python scripts/g07_run.py --menagerie <dir> --out evidence/G07
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from skuld.artifacts.hashing import entry_for_file
from skuld.core.protocol import PROTOCOL_V1, random_scenarios
from skuld.core.schemas import ArtifactKind, ArtifactManifest, EpisodeResult, Scenario
from skuld.oracle import evaluate as O
from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M
from skuld.policies.push_controller import POLICY_ID, PushController
from skuld.sim.episode import run_episode
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

P = PROTOCOL_V1
SPEC = PUSH_SPEC_V1
DOMAIN = P.domain


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--menagerie", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    for sub in ("nominal", "random", "spotcheck"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    if not SPEC.is_approved:
        print("refusing: TestSpec is not human-approved", file=sys.stderr)
        return 2
    if P.policy_ref != POLICY_ID:
        print(f"refusing: protocol policy_ref {P.policy_ref} != {POLICY_ID}", file=sys.stderr)
        return 2

    (out / "protocol.json").write_text(P.model_dump_json(indent=2))
    (out / "protocol_sha256.txt").write_text(P.digest() + "\n")
    (out / "heldout_configs.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in P.held_out_configs], indent=2)
    )

    adapter = MuJoCoPushAdapter(args.menagerie, render=False)
    policy = PushController(adapter.staged.scene_xml)
    manifest = policy.manifest()
    (out / "policy_manifest.json").write_text(manifest.model_dump_json(indent=2))

    def run_and_judge(sc: Scenario, folder: Path, *, video: Path | None = None, ad=None):
        ad = ad or adapter
        t0 = time.perf_counter()
        ep = run_episode(
            ad,
            policy,
            sc,
            DOMAIN,
            policy_ref=POLICY_ID,
            max_time_s=SPEC.deadline_s,
            goal_radius_m=SPEC.goal.target_radius_m,
            hold_steps=SPEC.goal.stability_steps,
            video_path=video,
        )
        wall = time.perf_counter() - t0
        traj_path = folder / f"{sc.scenario_id}.trajectory.json.gz"
        with gzip.open(traj_path, "wt", encoding="utf-8") as fh:
            fh.write(ep.trajectory.model_dump_json())
        r = O.evaluate(
            ep.trajectory,
            SPEC,
            target_xy=TARGET_XY_M,
            distance_from_nominal=sc.distance_from_nominal(DOMAIN),
            wallclock_s=wall,
            artifact_uris=[str(traj_path.relative_to(out))],
        )
        (folder / f"{sc.scenario_id}.result.json").write_text(r.model_dump_json(indent=2))
        return ep, r, wall

    def row(i: int, sc: Scenario, r: EpisodeResult, wall: float) -> dict:
        v0 = r.violations[0] if r.violations else None
        d = {"index": i, "scenario_id": sc.scenario_id, "seed": sc.seed}
        d.update({k: round(v, 6) for k, v in sc.values.items()})
        d.update(
            status=r.status.value,
            valid_failure=r.status.is_valid_failure,
            distance_from_nominal=round(r.distance_from_nominal, 6),
            robustness_m=None if r.robustness is None else round(r.robustness, 5),
            first_violation=v0.rule if v0 else "",
            violation_step=v0.step if v0 else "",
            wallclock_s=round(wall, 3),
            trajectory_sha256_source="manifest.json",
        )
        return d

    # ---- 1. nominal runs ------------------------------------------------------
    nominal_rows, nominal_digests = [], []
    for seed in P.seeds.nominal:
        sc = Scenario(
            scenario_id=f"nominal-s{seed}",
            domain_ref=DOMAIN.domain_id,
            values=DOMAIN.nominal_values(),
            seed=seed,
        )
        ep, r, wall = run_and_judge(sc, out / "nominal")
        nominal_rows.append(row(len(nominal_rows), sc, r, wall))
        nominal_digests.append(
            hashlib.sha256(
                json.dumps([st.model_dump(mode="json") for st in ep.trajectory.steps]).encode()
            ).hexdigest()
        )
        print(f"nominal seed={seed}: {r.status.value} wall={wall:.1f}s")
    nominal_identical = len(set(nominal_digests)) == 1
    print("nominal runs identical (ignoring id):", nominal_identical)

    # ---- 2. random baseline ---------------------------------------------------
    scenarios = random_scenarios(
        DOMAIN,
        P.budget.n_random,
        sampler_seed=P.sampler_seeds.random_baseline,
        prefix="rand",
        first_seed=0,
    )
    rows, curve = [], []
    failures_found, running_min, first_fail_idx, first_fail_wall = 0, math.inf, None, None
    cum_wall = 0.0
    for i, sc in enumerate(scenarios):
        ep, r, wall = run_and_judge(sc, out / "random")
        cum_wall += wall
        rows.append(row(i, sc, r, wall))
        if r.status.is_valid_failure:
            failures_found += 1
            running_min = min(running_min, r.distance_from_nominal)
            if first_fail_idx is None:
                first_fail_idx, first_fail_wall = i, cum_wall
        curve.append(
            {
                "cumulative_episodes": i + 1,
                "valid_failures_found": failures_found,
                "running_min_distance": None if math.isinf(running_min) else running_min,
                "cumulative_wallclock_s": round(cum_wall, 2),
            }
        )
        print(
            f"rand {i:03d}: {r.status.value:11s} dist={r.distance_from_nominal:.3f} "
            f"{[v.rule for v in r.violations]} wall={wall:.1f}s"
        )

    with (out / "random_baseline.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="
", fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with (out / "random_baseline_curve.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="
", fieldnames=list(curve[0].keys()))
        w.writeheader()
        w.writerows(curve)
    with (out / "nominal_runs.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="
", fieldnames=list(nominal_rows[0].keys()))
        w.writeheader()
        w.writerows(nominal_rows)

    # ---- 3. spot-check: replay first failure and first pass, compare -----------
    spot = []
    picks = []
    if first_fail_idx is not None:
        picks.append(("first_valid_failure", first_fail_idx))
    first_pass = next((i for i, rr in enumerate(rows) if rr["status"] == "PASS"), None)
    if first_pass is not None:
        picks.append(("first_pass", first_pass))
    for label, idx in picks:
        sc = scenarios[idx]
        orig = json.loads(
            gzip.open(out / "random" / f"{sc.scenario_id}.trajectory.json.gz", "rt").read()
        )
        ep, r, wall = run_and_judge(sc, out / "spotcheck")
        rep = json.loads(ep.trajectory.model_dump_json())
        same_traj = orig["steps"] == rep["steps"]
        same_status = rows[idx]["status"] == r.status.value
        spot.append(
            {
                "label": label,
                "scenario_id": sc.scenario_id,
                "bit_identical": same_traj,
                "same_verdict": same_status,
                "status": r.status.value,
            }
        )
        print(
            f"spot-check {label} {sc.scenario_id}: identical={same_traj} same_verdict={same_status}"
        )

    # ---- 4. one video: the first random failure -------------------------------
    video_info = None
    if first_fail_idx is not None and not args.no_video:
        sc = scenarios[first_fail_idx]
        vad = MuJoCoPushAdapter(args.menagerie, render=True)
        vpath = out / "first_random_failure.mp4"
        ep, r, wall = run_and_judge(sc, out / "spotcheck", video=vpath, ad=vad)
        video_info = {
            "scenario_id": sc.scenario_id,
            "path": vpath.name,
            "frames": ep.video_frames,
            "status": r.status.value,
            "wallclock_s": round(wall, 1),
        }
        print("video:", video_info)

    # ---- 5. metrics, manifest, report -----------------------------------------
    metrics = {
        "episodes_to_first_valid_failure": None if first_fail_idx is None else first_fail_idx + 1,
        "valid_failures_within_budget": failures_found,
        "min_distance_from_nominal_among_valid_failures": None
        if math.isinf(running_min)
        else running_min,
        "wallclock_s_to_first_valid_failure": None
        if first_fail_wall is None
        else round(first_fail_wall, 2),
        "budget_n_random": P.budget.n_random,
        "status_counts": {
            s: sum(1 for rr in rows if rr["status"] == s)
            for s in sorted({rr["status"] for rr in rows})
        },
        "total_wallclock_s": round(cum_wall, 1),
        "mean_wallclock_s_per_episode": round(cum_wall / len(rows), 2),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    entries = []
    for p in sorted(out.rglob("*")):
        # the run log is still being written by tee while this runs; it cannot be hashed here
        if p.is_file() and p.name not in ("manifest.json", "g07_run.log"):
            entries.append(
                entry_for_file(
                    p,
                    root=out,
                    producer="scripts/g07_run.py",
                    kind=ArtifactKind.RAW if p.suffix == ".gz" else ArtifactKind.DERIVED,
                )
            )
    man = ArtifactManifest(
        manifest_id="g07-evidence",
        correlation_id=f"g07-{P.digest()[:12]}",
        created_at=datetime.now(UTC),
        entries=entries,
    )
    (out / "manifest.json").write_text(man.model_dump_json(indent=2))

    report = {
        "gate": "G07",
        "protocol_sha256": P.digest(),
        "spec_sha256": SPEC.digest(),
        "spec_approved_by": SPEC.approved_by,
        "policy_id": POLICY_ID,
        "policy_source_sha256": manifest.source_sha256,
        "scene_sha256": adapter.staged.scene_sha256,
        "sim": f"{adapter.sim_name} {adapter.sim_version}",
        "nominal": {
            "runs": len(nominal_rows),
            "statuses": [r["status"] for r in nominal_rows],
            "bit_identical": nominal_identical,
        },
        "random_baseline": metrics,
        "spot_checks": spot,
        "video": video_info,
        "artifact_count": len(entries),
    }
    (out / "g07_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    ok = nominal_identical and all(s["bit_identical"] and s["same_verdict"] for s in spot)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
