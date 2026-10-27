"""G06 evidence run: apply the deterministic oracle to the saved G05 trajectories
and to deliberately broken copies of them (fault injection, spec 9).

Runs in the app venv: no MuJoCo needed, only the JSON artifacts.

Usage: python scripts/g06_run.py --g05 evidence/G05 --out evidence/G06 [--approved-by NAME]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

from skuld.core.domains import PUSH_V1
from skuld.core.schemas import EpisodeStatus, Scenario
from skuld.oracle import evaluate as O
from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M, approve


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--g05", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--approved-by",
        default=None,
        help="Name of the human approving PUSH_SPEC_V1 for this run. Without it the run is "
        "PROVISIONAL and every result says so.",
    )
    args = ap.parse_args()
    g05, out = Path(args.g05), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "episode_results").mkdir(exist_ok=True)

    spec = approve(PUSH_SPEC_V1, args.approved_by) if args.approved_by else PUSH_SPEC_V1
    spec_json = spec.model_dump_json(indent=2)
    (out / "test_spec.json").write_text(spec_json)
    (out / "test_spec_sha256.txt").write_text(spec.digest() + "\n")

    g05_report = json.loads((g05 / "g05_run_report.json").read_text())
    rows = []
    for name, ep in g05_report["episodes"].items():
        sc = Scenario.model_validate(ep["scenario"])
        path = g05 / f"{name}.trajectory.json"
        r = O.evaluate_file(
            path,
            spec,
            target_xy=TARGET_XY_M,
            distance_from_nominal=sc.distance_from_nominal(PUSH_V1),
            scenario_ref=sc.scenario_id,
            policy_ref=g05_report["policy_id"],
            wallclock_s=ep["wallclock_s"],
            allow_unapproved=not spec.is_approved,
        )
        (out / "episode_results" / f"{name}.json").write_text(r.model_dump_json(indent=2))
        rows.append(
            {
                "episode": name,
                "status": r.status.value,
                "valid_failure": r.status.is_valid_failure,
                "violations": [v.model_dump() for v in r.violations],
                "robustness_m": r.robustness,
                "distance_from_nominal": r.distance_from_nominal,
                "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "detail": r.detail,
            }
        )
        print(f"{name:14s} {r.status.value:12s} {[v.rule for v in r.violations]}")

    # --- fault injection: broken copies must come out INVALID, never PASS -------
    faults = out / "fault_injection"
    if faults.exists():
        shutil.rmtree(faults)
    faults.mkdir()
    src = g05 / "nominal.trajectory.json"
    good = json.loads(src.read_text())
    cases: dict[str, bytes] = {}
    cases["truncated.json"] = src.read_bytes()[: len(src.read_bytes()) // 2]
    d = json.loads(json.dumps(good))
    d["steps"][50]["qpos"][0] = None
    cases["missing_value.json"] = json.dumps(d).encode()
    d = json.loads(json.dumps(good))
    d["steps"][50]["object_pos_m"][2] = -0.5
    cases["block_below_floor.json"] = json.dumps(d).encode()
    d = json.loads(json.dumps(good))
    d["steps"][100]["sim_time_s"] += 0.5
    cases["timebase_jump.json"] = json.dumps(d).encode()
    d = json.loads(json.dumps(good))
    d["oracle_verdict"] = "PASS"
    cases["injected_verdict_field.json"] = json.dumps(d).encode()
    d = json.loads(json.dumps(good))
    d["steps"] = d["steps"][:100]  # cut long before the deadline, goal not yet reached
    cases["truncated_run.json"] = json.dumps(d).encode()
    fault_rows = []
    for fname, blob in cases.items():
        p = faults / fname
        p.write_bytes(blob)
        r = O.evaluate_file(
            p,
            spec,
            target_xy=TARGET_XY_M,
            distance_from_nominal=0.0,
            scenario_ref="nominal",
            policy_ref=g05_report["policy_id"],
            allow_unapproved=not spec.is_approved,
        )
        expected = EpisodeStatus.TIMEOUT if fname == "truncated_run.json" else EpisodeStatus.INVALID
        fault_rows.append(
            {
                "file": fname,
                "status": r.status.value,
                "expected": expected.value,
                "as_expected": r.status is expected,
                "detail": r.detail,
            }
        )
        print(f"fault {fname:28s} -> {r.status.value:8s} (expected {expected.value})")
    e = O.exec_error_result(
        episode_id="simulated-infra-failure", error="simulated: job status unknown", spec=spec
    )
    fault_rows.append(
        {
            "file": "<no artifact>",
            "status": e.status.value,
            "expected": "EXEC_ERROR",
            "as_expected": e.status is EpisodeStatus.EXEC_ERROR,
            "detail": e.detail,
        }
    )

    report = {
        "gate": "G06",
        "spec_ref": f"{spec.spec_id}-v{spec.version}",
        "spec_sha256": spec.digest(),
        "spec_approved_by": spec.approved_by,
        "target_xy_m": list(TARGET_XY_M),
        "g05_scene_sha256": g05_report["scene_sha256"],
        "policy_id": g05_report["policy_id"],
        "episodes": rows,
        "fault_injection": fault_rows,
        "status_counts": {
            s.value: sum(1 for r in rows if r["status"] == s.value)
            for s in EpisodeStatus
            if s is not EpisodeStatus.RUNNING
        },
        "all_faults_fail_closed": all(fr["as_expected"] for fr in fault_rows),
    }
    (out / "g06_oracle_report.json").write_text(json.dumps(report, indent=2))
    print("status counts:", report["status_counts"])
    print("faults fail closed:", report["all_faults_fail_closed"])
    bad = [
        r for r in rows if r["robustness_m"] is not None and not math.isfinite(r["robustness_m"])
    ]
    return 0 if report["all_faults_fail_closed"] and not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
