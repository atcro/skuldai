"""G12 frozen-code rerun: nominal, random and active search for every registered
policy, same protocol, same budgets, same sampler seeds. Produces the results
table the README publishes and checks that the rerun of the policy under test
reproduces the archived G07 and G10 episodes byte for byte.

Usage (sim venv):
  MUJOCO_GL=egl python scripts/g12_run.py --menagerie <dir> --out evidence/G12
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from skuld.artifacts.hashing import entry_for_file
from skuld.core.protocol import PROTOCOL_V1, random_scenarios
from skuld.core.schemas import ArtifactKind, ArtifactManifest, Scenario
from skuld.oracle import evaluate as O
from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M
from skuld.policies import push_controller as v1
from skuld.policies import push_controller_v2 as v2
from skuld.search import ActiveSearchConfig, Outcome, active_search
from skuld.search.objective import Ledger
from skuld.sim.episode import run_episode
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

P = PROTOCOL_V1
SPEC = PUSH_SPEC_V1
DOMAIN = P.domain


def steps_sha(traj_json: str) -> str:
    return hashlib.sha256(json.dumps(json.loads(traj_json)["steps"]).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--menagerie", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--g07", default="evidence/G07")
    ap.add_argument("--g10", default="evidence/G10")
    ap.add_argument("--g11", default="evidence/G11")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    # the evidence folder this run writes is the only thing allowed to be untracked
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", ".", f":!{out.as_posix()}"], text=True
    ).strip()
    (out / "frozen_commit.txt").write_text(f"{sha}\ndirty_tree: {bool(dirty)}\n")

    adapter = MuJoCoPushAdapter(args.menagerie, render=False)
    policies = {
        v1.POLICY_ID: v1.PushController(adapter.staged.scene_xml),
        v2.POLICY_ID: v2.PushControllerV2(adapter.staged.scene_xml),
    }
    folder = {"path": out}

    def run_and_judge(pid: str, sc: Scenario):
        t0 = time.perf_counter()
        ep = run_episode(
            adapter,
            policies[pid],
            sc,
            DOMAIN,
            policy_ref=pid,
            max_time_s=SPEC.deadline_s,
            goal_radius_m=SPEC.goal.target_radius_m,
            hold_steps=SPEC.goal.stability_steps,
        )
        wall = time.perf_counter() - t0
        tj = ep.trajectory.model_dump_json()
        tp = folder["path"] / f"{sc.scenario_id}.trajectory.json.gz"
        with gzip.open(tp, "wt", encoding="utf-8") as fh:
            fh.write(tj)
        r = O.evaluate(
            ep.trajectory,
            SPEC,
            target_xy=TARGET_XY_M,
            distance_from_nominal=sc.distance_from_nominal(DOMAIN),
            wallclock_s=wall,
            artifact_uris=[str(tp.relative_to(out))],
        )
        (folder["path"] / f"{sc.scenario_id}.result.json").write_text(r.model_dump_json(indent=2))
        return r, wall, steps_sha(tj)

    def make_objective(pid: str, hashes: dict[str, str]):
        def objective(vals, sid, seed) -> Outcome:
            sc = Scenario(
                scenario_id=sid, domain_ref=DOMAIN.domain_id, values=dict(vals), seed=seed
            )
            r, wall, h = run_and_judge(pid, sc)
            hashes[sid] = h
            print(
                f"{sid}: {r.status.value:11s} dist={r.distance_from_nominal:.3f} wall={wall:.1f}s"
            )
            return Outcome(r.status, robustness=r.robustness, wallclock_s=wall)

        return objective

    table: dict[str, dict] = {}
    repro: dict[str, dict] = {}
    for pid in policies:
        print(f"=== {pid} ===")
        row: dict = {"policy": pid}
        # nominal
        folder["path"] = out / pid / "nominal"
        folder["path"].mkdir(parents=True, exist_ok=True)
        nom = []
        for seed in P.seeds.nominal:
            sc = Scenario(
                scenario_id=f"nominal-s{seed}",
                domain_ref=DOMAIN.domain_id,
                values=DOMAIN.nominal_values(),
                seed=seed,
            )
            r, wall, h = run_and_judge(pid, sc)
            nom.append((r.status.value, wall, h))
            print(f"nominal s{seed}: {r.status.value}")
        row["nominal"] = {
            "episodes": len(nom),
            "statuses": [s for s, _, _ in nom],
            "bit_identical": len({h for _, _, h in nom}) == 1,
            "wallclock_s": round(sum(w for _, w, _ in nom), 1),
        }
        # random, same sampler seed and budget as G07
        folder["path"] = out / pid / "random"
        folder["path"].mkdir(parents=True, exist_ok=True)
        hashes: dict[str, str] = {}
        objective = make_objective(pid, hashes)
        rnd = Ledger(DOMAIN, objective, P.budget.n_random, "rand")

        for sc in random_scenarios(
            DOMAIN,
            P.budget.n_random,
            sampler_seed=P.sampler_seeds.random_baseline,
            prefix="rand",
            first_seed=0,
        ):
            rnd.evaluate(sc.values, phase="random", move="uniform", seed=sc.seed)
        row["random"] = rnd.metrics()
        random_hashes = dict(hashes)
        # active, same config as G10
        folder["path"] = out / pid / "active"
        folder["path"].mkdir(parents=True, exist_ok=True)
        hashes.clear()
        cfg = ActiveSearchConfig(
            budget=P.budget.n_active, sampler_seed=P.sampler_seeds.active_search
        )
        act = active_search(DOMAIN, objective, cfg, prefix="act")
        (out / pid / "active_search.json").write_text(act.model_dump_json(indent=2))
        row["active"] = act.metrics
        row["active_best"] = None if act.best is None else act.best.model_dump(mode="json")
        active_hashes = dict(hashes)
        table[pid] = row

        # reproduction against the archived evidence (policy under test only)
        if pid == v1.POLICY_ID:

            def archived(root: Path, sid: str) -> str:
                p = root / f"{sid}.trajectory.json.gz"
                return steps_sha(gzip.open(p, "rt").read()) if p.exists() else "missing"

            rr = {
                sid: archived(Path(args.g07) / "random", sid) == h
                for sid, h in random_hashes.items()
            }
            ra = {
                sid: archived(Path(args.g10) / "active", sid) == h
                for sid, h in active_hashes.items()
            }
            repro = {
                "random_vs_G07": {"identical": sum(rr.values()), "of": len(rr)},
                "active_vs_G10": {"identical": sum(ra.values()), "of": len(ra)},
                "mismatches": [k for k, v in {**rr, **ra}.items() if not v],
            }
            print("reproduction:", json.dumps(repro))

    # held-out and release decisions come from G11 (not re-run here; same commit)
    g11 = json.loads((Path(args.g11) / "g11_report.json").read_text())
    g10 = json.loads((Path(args.g10) / "g10_report.json").read_text())

    def pub(pid: str) -> dict:
        t = table[pid]
        r, a = t["random"], t["active"]
        return {
            "episodes_used": {
                "nominal": t["nominal"]["episodes"],
                "random": r["episodes_used"],
                "active": a["episodes_used"],
            },
            "failures_found": {
                "nominal": sum(s != "PASS" for s in t["nominal"]["statuses"]),
                "random": r["valid_failures_within_budget"],
                "active": a["valid_failures_within_budget"],
            },
            "episodes_to_first_failure": {
                "random": r["episodes_to_first_valid_failure"],
                "active": a["episodes_to_first_valid_failure"],
            },
            "closest_failure_distance": {
                "random": r["min_distance_from_nominal_among_valid_failures"],
                "active": a["min_distance_from_nominal_among_valid_failures"],
            },
            "compute_s": {
                "nominal": t["nominal"]["wallclock_s"],
                "random": r["total_wallclock_s"],
                "active": a["total_wallclock_s"],
            },
            "held_out_G11": g11["results"][pid]["held_out"],
            "regression_G11": g11["results"][pid]["regression"],
            "release_decision_G11": g11["decisions"][pid]["status"],
        }

    entries = [
        entry_for_file(
            p,
            root=out,
            producer="scripts/g12_run.py",
            kind=ArtifactKind.RAW if p.suffix == ".gz" else ArtifactKind.DERIVED,
        )
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name not in ("manifest.json", "g12_run.log")
    ]
    man = ArtifactManifest(
        manifest_id="g12-evidence",
        correlation_id=f"g12-{sha[:12]}",
        created_at=datetime.now(UTC),
        entries=entries,
    )
    (out / "manifest.json").write_text(man.model_dump_json(indent=2))

    report = {
        "gate": "G12",
        "frozen_commit": sha,
        "dirty_tree": bool(dirty),
        "protocol_sha256": P.digest(),
        "sim": f"{adapter.sim_name} {adapter.sim_version}",
        "scene_sha256": adapter.staged.scene_sha256,
        "policies": {pid: policies[pid].manifest().source_sha256 for pid in policies},
        "results": {pid: pub(pid) for pid in policies},
        "raw": table,
        "reproduction_of_archived_runs": repro,
        "minimized_counterexample_G10": g10["minimization"]["minimized"],
        "artifact_count": len(entries),
        "written_utc": datetime.now(UTC).isoformat(),
    }
    (out / "g12_report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps({k: report[k] for k in ("results", "reproduction_of_archived_runs")}, indent=2)
    )
    ok = all(v["identical"] == v["of"] for k, v in repro.items() if k != "mismatches")
    ok = ok and all(t["nominal"]["bit_identical"] for t in table.values())
    return 0 if ok and not dirty else 1


if __name__ == "__main__":
    raise SystemExit(main())
