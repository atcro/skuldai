"""G10 evidence run: active search on the locked protocol, matched against the
archived G07 random baseline, then counterexample minimization, seed-set replay
and two videos (original and minimized failure).

Every episode is stored (gzipped Trajectory + oracle EpisodeResult) and hashed
into a manifest. Nothing from G07 is re-run or edited: the comparison reads the
archived baseline and refuses to run if protocol, policy or scene have changed.

Usage (sim venv):
  MUJOCO_GL=egl python scripts/g10_run.py --menagerie <dir> --out evidence/G10 \
      --baseline evidence/G07 [--hypothesis evidence/G08/hypothesis.json] [--no-video]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from skuld.artifacts.hashing import entry_for_file
from skuld.core.protocol import PROTOCOL_V1
from skuld.core.schemas import (
    ArtifactKind,
    ArtifactManifest,
    Counterexample,
    EpisodeStatus,
    Hypothesis,
    Scenario,
)
from skuld.oracle import evaluate as O
from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M
from skuld.policies.push_controller import POLICY_ID, PushController
from skuld.search import (
    ActiveSearchConfig,
    Candidate,
    MinimizationConfig,
    Outcome,
    active_search,
    minimize_failure,
)
from skuld.search.objective import CurvePoint
from skuld.search.plot import write_comparison_svg
from skuld.sim.episode import run_episode
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

P = PROTOCOL_V1
SPEC = PUSH_SPEC_V1
DOMAIN = P.domain
LF = "\n"
REPLAY_SEEDS = [0, 1, 2]
VAR_NAMES = [v.name for v in DOMAIN.variables]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator=LF, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def ledger_rows(cands: list[Candidate]) -> list[dict]:
    rows = []
    for c in cands:
        d = {
            "index": c.index,
            "scenario_id": c.scenario_id,
            "phase": c.phase,
            "move": c.move,
            "parent": c.parent or "",
            "seed": c.seed,
        }
        d.update({k: round(c.values[k], 6) for k in VAR_NAMES})
        d.update(
            status=c.status.value,
            valid_failure=c.valid_failure,
            accepted=c.accepted,
            counts_against_budget=c.counts_against_budget,
            distance_from_nominal=round(c.distance_from_nominal, 6),
            robustness_m=None if c.robustness is None else round(c.robustness, 5),
            wallclock_s=round(c.wallclock_s, 3),
            note=c.note,
        )
        rows.append(d)
    return rows


def load_baseline_curve(baseline: Path) -> list[CurvePoint]:
    pts = []
    with (baseline / "random_baseline_curve.csv").open(newline="") as fh:
        for r in csv.DictReader(fh):
            rm = r["running_min_distance"]
            pts.append(
                CurvePoint(
                    cumulative_episodes=int(r["cumulative_episodes"]),
                    valid_failures_found=int(r["valid_failures_found"]),
                    running_min_distance=None if rm in ("", "None") else float(rm),
                    cumulative_wallclock_s=float(r["cumulative_wallclock_s"]),
                )
            )
    return pts


def baseline_nearest_failure(baseline: Path) -> dict | None:
    best = None
    with (baseline / "random_baseline.csv").open(newline="") as fh:
        for r in csv.DictReader(fh):
            if r["valid_failure"] == "True":
                d = float(r["distance_from_nominal"])
                if best is None or d < best[0]:
                    best = (d, r)
    if best is None:
        return None
    r = best[1]
    return {"scenario_id": r["scenario_id"], "values": {k: float(r[k]) for k in VAR_NAMES}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--menagerie", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--baseline", default="evidence/G07")
    ap.add_argument("--hypothesis", default=None)
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    out, baseline = Path(args.out), Path(args.baseline)
    for sub in ("active", "active_hyp", "minimize", "replay"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    # ---- preflight: same protocol, spec, policy and scene as the archived baseline -------
    if not SPEC.is_approved:
        print("refusing: TestSpec is not human-approved", file=sys.stderr)
        return 2
    if P.policy_ref != POLICY_ID:
        print(f"refusing: protocol policy_ref {P.policy_ref} != {POLICY_ID}", file=sys.stderr)
        return 2
    g07_sha = (baseline / "protocol_sha256.txt").read_text().strip()
    if g07_sha != P.digest():
        print(f"refusing: protocol digest {P.digest()} != baseline {g07_sha}", file=sys.stderr)
        return 2
    g07 = json.loads((baseline / "g07_report.json").read_text())

    adapter = MuJoCoPushAdapter(args.menagerie, render=False)
    policy = PushController(adapter.staged.scene_xml)
    manifest = policy.manifest()
    if manifest.source_sha256 != g07["policy_source_sha256"]:
        print("refusing: policy source changed since the baseline; comparison not matched")
        return 2
    if adapter.staged.scene_sha256 != g07["scene_sha256"]:
        print("refusing: scene changed since the baseline; comparison not matched")
        return 2
    (out / "protocol_sha256.txt").write_text(P.digest() + "\n")
    (out / "policy_manifest.json").write_text(manifest.model_dump_json(indent=2))
    print(
        f"preflight ok: protocol {P.digest()[:12]} policy {manifest.source_sha256[:12]} "
        f"scene {adapter.staged.scene_sha256[:12]}"
    )

    # ---- the objective: run, store, judge. The search never sees a trajectory. ---------
    folder = {"path": out / "active"}
    stored: dict[str, dict] = {}  # scenario_id -> {"result": EpisodeResult, "steps_sha256": str}

    def run_and_judge(sc: Scenario, *, video: Path | None = None, ad=None):
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
        traj_path = folder["path"] / f"{sc.scenario_id}.trajectory.json.gz"
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
        (folder["path"] / f"{sc.scenario_id}.result.json").write_text(r.model_dump_json(indent=2))
        steps_sha = hashlib.sha256(
            json.dumps([st.model_dump(mode="json") for st in ep.trajectory.steps]).encode()
        ).hexdigest()
        stored[sc.scenario_id] = {"result": r, "steps_sha256": steps_sha, "frames": ep.video_frames}
        return r, wall

    def objective(values, scenario_id, seed) -> Outcome:
        sc = Scenario(
            scenario_id=scenario_id, domain_ref=DOMAIN.domain_id, values=dict(values), seed=seed
        )
        t0 = time.perf_counter()
        try:
            r, wall = run_and_judge(sc)
        except Exception as e:  # infrastructure failure: EXEC_ERROR, never a verdict
            wall = time.perf_counter() - t0
            r = O.exec_error_result(
                episode_id=f"traj-{scenario_id}-s{seed}",
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}",
                spec=SPEC,
                scenario_ref=scenario_id,
                policy_ref=POLICY_ID,
                distance_from_nominal=DOMAIN.distance(values),
                wallclock_s=wall,
            )
            (folder["path"] / f"{scenario_id}.result.json").write_text(r.model_dump_json(indent=2))
        print(
            f"{scenario_id}: {r.status.value:11s} dist={r.distance_from_nominal:.3f} "
            f"{[v.rule for v in r.violations]} wall={wall:.1f}s"
        )
        return Outcome(r.status, robustness=r.robustness, wallclock_s=wall)

    # ---- 1. active search, matched budget, no prior ------------------------------------
    cfg = ActiveSearchConfig(budget=P.budget.n_active, sampler_seed=P.sampler_seeds.active_search)
    print(f"=== active search ({cfg.method}), budget {cfg.budget}, seed {cfg.sampler_seed} ===")
    folder["path"] = out / "active"
    active = active_search(DOMAIN, objective, cfg, prefix="act")
    (out / "active_search.json").write_text(active.model_dump_json(indent=2))
    write_csv(out / "active_ledger.csv", ledger_rows(active.candidates))
    write_csv(out / "active_curve.csv", [p.model_dump() for p in active.curve])
    print("active metrics:", json.dumps(active.metrics))

    # ---- 2. optional: exploration seeded by the approved G08 hypothesis ----------------
    active_hyp = None
    if args.hypothesis:
        h = Hypothesis.model_validate_json(Path(args.hypothesis).read_text())
        h.check_against(DOMAIN)
        box = {v.name: (v.min, v.max) for v in h.variables}
        cfg_h = cfg.model_copy(update={"explore_box": box})
        print(f"=== active search with hypothesis box {box} (not the matched comparison) ===")
        folder["path"] = out / "active_hyp"
        active_hyp = active_search(DOMAIN, objective, cfg_h, prefix="acth")
        (out / "active_hyp_search.json").write_text(active_hyp.model_dump_json(indent=2))
        write_csv(out / "active_hyp_ledger.csv", ledger_rows(active_hyp.candidates))
        write_csv(out / "active_hyp_curve.csv", [p.model_dump() for p in active_hyp.curve])
        print("active+hypothesis metrics:", json.dumps(active_hyp.metrics))

    # ---- 3. comparison against the archived random baseline ----------------------------
    g07_metrics = json.loads((baseline / "metrics.json").read_text())
    series = {"random (G07, archived)": load_baseline_curve(baseline), "active": active.curve}
    if active_hyp is not None:
        series["active + G08 hypothesis box"] = active_hyp.curve
    write_comparison_svg(
        out / "comparison.svg",
        series,
        budget=P.budget.n_active,
        caption=f"protocol {P.digest()[:12]}; policy {POLICY_ID}; same domain, oracle and budget; "
        f"random curve read from {baseline}/random_baseline_curve.csv",
    )
    comparison = {
        "protocol_sha256": P.digest(),
        "budget_per_strategy": P.budget.n_active,
        "random_baseline_G07": g07_metrics,
        "active": active.metrics,
        "active_with_hypothesis_box": None if active_hyp is None else active_hyp.metrics,
        "active_beats_random_on_first_failure": (
            active.metrics["episodes_to_first_valid_failure"] is not None
            and (
                g07_metrics["episodes_to_first_valid_failure"] is None
                or active.metrics["episodes_to_first_valid_failure"]
                < g07_metrics["episodes_to_first_valid_failure"]
            )
        ),
        "active_beats_random_on_min_distance": (
            active.metrics["min_distance_from_nominal_among_valid_failures"] is not None
            and (
                g07_metrics["min_distance_from_nominal_among_valid_failures"] is None
                or active.metrics["min_distance_from_nominal_among_valid_failures"]
                < g07_metrics["min_distance_from_nominal_among_valid_failures"]
            )
        ),
        "note": "one run per strategy at a budget of 25; a difference of a few episodes is not "
        "statistically meaningful and is reported as observed, not as a trend",
    }
    (out / "comparison.json").write_text(json.dumps(comparison, indent=2))
    print("comparison:", json.dumps(comparison, indent=2))

    # ---- 4. minimization of the nearest observed failure --------------------------------
    source, target_values, target_id = None, None, None
    if active.best is not None:
        source, target_values, target_id = "active", active.best.values, active.best.scenario_id
    elif active_hyp is not None and active_hyp.best is not None:
        source = "active_with_hypothesis_box"
        target_values, target_id = active_hyp.best.values, active_hyp.best.scenario_id
    else:
        nearest = baseline_nearest_failure(baseline)
        if nearest is not None:
            source, target_values, target_id = (
                "random_G07",
                nearest["values"],
                nearest["scenario_id"],
            )
    if target_values is None:
        print("no valid failure found by any strategy; nothing to minimize", file=sys.stderr)
        report = {"gate": "G10", "comparison": comparison, "minimization": None}
        (out / "g10_report.json").write_text(json.dumps(report, indent=2))
        return 1

    print(f"=== minimizing {target_id} from {source}: {target_values} ===")
    folder["path"] = out / "minimize"
    mcfg = MinimizationConfig(seeds=[0])  # deterministic simulator: one seed per step (protocol)
    mres = minimize_failure(DOMAIN, dict(target_values), objective, mcfg, prefix="min")
    (out / "minimization.json").write_text(mres.model_dump_json(indent=2))
    write_csv(out / "minimize_ledger.csv", ledger_rows(mres.candidates))
    print(
        "minimization:",
        mres.status,
        "removed",
        mres.removed_variables,
        "kept",
        mres.kept_variables,
        f"distance {mres.initial_distance:.3f} -> {mres.minimized_distance:.3f}",
    )
    if mres.status != "minimized":
        report = {
            "gate": "G10",
            "comparison": comparison,
            "minimization": mres.model_dump(mode="json"),
        }
        (out / "g10_report.json").write_text(json.dumps(report, indent=2))
        return 1

    # ---- 5. replay the minimized scenario on the seed set; check reproduction -----------
    folder["path"] = out / "replay"
    replays = []
    for s in REPLAY_SEEDS:
        sc = Scenario(
            scenario_id=f"minimized-s{s}",
            domain_ref=DOMAIN.domain_id,
            values=mres.minimized_values,
            seed=s,
        )
        r, wall = run_and_judge(sc)
        replays.append(
            {
                "seed": s,
                "status": r.status.value,
                "steps_sha256": stored[sc.scenario_id]["steps_sha256"],
                "wallclock_s": round(wall, 3),
            }
        )
        print(f"replay seed {s}: {r.status.value}")
    replay_failures = sum(1 for x in replays if EpisodeStatus(x["status"]).is_valid_failure)
    bit_identical = len({x["steps_sha256"] for x in replays}) == 1

    # ---- 6. videos: original and minimized ---------------------------------------------
    videos = {}
    if not args.no_video:
        vad = MuJoCoPushAdapter(args.menagerie, render=True)
        for label, values in (("original", target_values), ("minimized", mres.minimized_values)):
            sc = Scenario(
                scenario_id=f"{label}-video",
                domain_ref=DOMAIN.domain_id,
                values=dict(values),
                seed=0,
            )
            vpath = out / f"{label}_failure.mp4"
            r, wall = run_and_judge(sc, video=vpath, ad=vad)
            videos[label] = {
                "path": vpath.name,
                "status": r.status.value,
                "frames": stored[sc.scenario_id]["frames"],
                "wallclock_s": round(wall, 1),
            }
            print(f"video {label}: {videos[label]}")

    ce = Counterexample(
        counterexample_id=f"ce-{target_id}",
        original=Scenario(
            scenario_id=target_id, domain_ref=DOMAIN.domain_id, values=dict(target_values), seed=0
        ),
        minimized=Scenario(
            scenario_id="minimized",
            domain_ref=DOMAIN.domain_id,
            values=mres.minimized_values,
            seed=0,
        ),
        removed_variables=mres.removed_variables,
        kept_variables=mres.kept_variables,
        replay_seeds=REPLAY_SEEDS,
        replay_runs=len(replays),
        replay_failures=replay_failures,
        replay_video_uri=videos.get("minimized", {}).get("path"),
    )
    ce.check_minimized(DOMAIN)
    (out / "counterexample.json").write_text(ce.model_dump_json(indent=2))

    # ---- 7. manifest and report ----------------------------------------------------------
    entries = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name not in ("manifest.json", "g10_run.log"):
            entries.append(
                entry_for_file(
                    p,
                    root=out,
                    producer="scripts/g10_run.py",
                    kind=ArtifactKind.RAW if p.suffix == ".gz" else ArtifactKind.DERIVED,
                )
            )
    man = ArtifactManifest(
        manifest_id="g10-evidence",
        correlation_id=f"g10-{P.digest()[:12]}",
        created_at=datetime.now(UTC),
        entries=entries,
    )
    (out / "manifest.json").write_text(man.model_dump_json(indent=2))

    reproduced = replay_failures == len(replays) and bit_identical
    report = {
        "gate": "G10",
        "protocol_sha256": P.digest(),
        "spec_sha256": SPEC.digest(),
        "policy_id": POLICY_ID,
        "policy_source_sha256": manifest.source_sha256,
        "scene_sha256": adapter.staged.scene_sha256,
        "sim": f"{adapter.sim_name} {adapter.sim_version}",
        "search_method": active.method,
        "search_config": active.config.model_dump(mode="json"),
        "comparison": comparison,
        "active_incumbents": active.incumbents,
        "active_explore_episodes": active.explore_episodes,
        "active_contract_episodes": active.contract_episodes,
        "minimization_source": source,
        "minimization": {
            "status": mres.status,
            "initial": mres.initial_values,
            "minimized": mres.minimized_values,
            "initial_distance": mres.initial_distance,
            "minimized_distance": mres.minimized_distance,
            "removed_variables": mres.removed_variables,
            "kept_variables": mres.kept_variables,
            "non_monotone_variables": mres.non_monotone_variables,
            "refined": mres.refined,
            "episodes_used": mres.episodes_used,
            "exec_errors": mres.exec_errors,
        },
        "replay": {
            "seeds": REPLAY_SEEDS,
            "runs": replays,
            "failures": replay_failures,
            "bit_identical_steps": bit_identical,
            "note": "the simulator ignores the seed (deterministic); this is a "
            "reproducibility check, not a probability estimate",
        },
        "videos": videos,
        "artifact_count": len(entries),
        "reproduced": reproduced,
        "written_utc": datetime.now(UTC).isoformat(),
    }
    (out / "g10_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if reproduced else 1


if __name__ == "__main__":
    raise SystemExit(main())
