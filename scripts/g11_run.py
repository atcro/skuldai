"""G11 evidence run: test-suite registry, release candidates for the policy under
test (v1) and the repair attempt (v2), full suite execution for both, fail-closed
release decisions, and fault injection against the stored evidence.

Usage (sim venv):
  MUJOCO_GL=egl python scripts/g11_run.py --menagerie <dir> --out evidence/G11 \
      --g10 evidence/G10 [--no-video]
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from skuld.artifacts.hashing import entry_for_file, verify_entry
from skuld.core.protocol import PROTOCOL_V1
from skuld.core.schemas import (
    ArtifactKind,
    ArtifactManifest,
    Counterexample,
    EpisodeResult,
    ReleaseCandidate,
    ReleaseStatus,
    Scenario,
    SeedLists,
)
from skuld.oracle import evaluate as O
from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M
from skuld.policies import push_controller as v1
from skuld.policies import push_controller_v2 as v2
from skuld.release import (
    CaseEvidence,
    PolicyRegistry,
    build_suite,
    decide,
    regression_from_counterexample,
)
from skuld.sim.episode import run_episode
from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

P = PROTOCOL_V1
SPEC = PUSH_SPEC_V1
DOMAIN = P.domain
SUITES = ("nominal", "regression", "held_out")


def revalidated(r: EpisodeResult, **changes) -> EpisodeResult:
    """A modified copy that goes through full validation (model_copy would not)."""
    return EpisodeResult.model_validate({**r.model_dump(mode="json"), **changes})


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - absence of git is not a reason to fake a hash
        return "0000000"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--menagerie", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--g10", default="evidence/G10")
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    out, g10 = Path(args.out), Path(args.g10)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    sha = git_sha()

    if not SPEC.is_approved:
        print("refusing: TestSpec is not human-approved", file=sys.stderr)
        return 2

    # ---- 1. registries --------------------------------------------------------------
    adapter = MuJoCoPushAdapter(args.menagerie, render=False)
    policies = {
        v1.POLICY_ID: v1.PushController(adapter.staged.scene_xml),
        v2.POLICY_ID: v2.PushControllerV2(adapter.staged.scene_xml),
    }
    registry = PolicyRegistry(policies=[p.manifest() for p in policies.values()])
    (out / "policy_registry.json").write_text(registry.model_dump_json(indent=2))
    g10_manifest = json.loads((g10 / "policy_manifest.json").read_text())
    if registry.get(v1.POLICY_ID).source_sha256 != g10_manifest["source_sha256"]:
        print("refusing: v1 source hash differs from the G10 evidence", file=sys.stderr)
        return 2

    ce = Counterexample.model_validate_json((g10 / "counterexample.json").read_text())
    ce.check_minimized(DOMAIN)
    min_result = json.loads((g10 / "replay" / "minimized-s0.result.json").read_text())
    sig = f"{min_result['status']}: " + ", ".join(v["rule"] for v in min_result["violations"])
    regressions = regression_from_counterexample(
        ce, source_gate="G10", reproduced_failure=sig, created_at=now
    )
    suite = build_suite(P, regressions, created_at=now)
    (out / "test_suite.json").write_text(suite.model_dump_json(indent=2))
    print(
        f"suite {suite.ref}: {len(suite.nominal)} nominal, {len(suite.regression)} regression, "
        f"{len(suite.held_out)} held-out; commit {sha[:12]}"
    )

    # ---- 2. run every suite for every policy ---------------------------------------
    def run_case(policy_id: str, suite_name: str, sc: Scenario, *, video: Path | None = None):
        folder = out / policy_id / suite_name
        folder.mkdir(parents=True, exist_ok=True)
        ad = adapter if video is None else MuJoCoPushAdapter(args.menagerie, render=True)
        t0 = time.perf_counter()
        ep = run_episode(
            ad,
            policies[policy_id],
            sc,
            DOMAIN,
            policy_ref=policy_id,
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
        print(
            f"{policy_id} {suite_name}/{sc.scenario_id}: {r.status.value} "
            f"{[v.rule for v in r.violations]} wall={wall:.1f}s"
        )
        return r, traj_path

    results: dict[str, dict[str, list[tuple[Scenario, EpisodeResult, Path]]]] = {}
    for pid in policies:
        results[pid] = {}
        for s in SUITES:
            results[pid][s] = [(sc, *run_case(pid, s, sc)) for sc in suite.scenarios(s)]

    # ---- 3. manifest first, so artifact checks in the gate are against recorded hashes
    def manifest_entries():
        return [
            entry_for_file(
                p,
                root=out,
                producer="scripts/g11_run.py",
                kind=ArtifactKind.RAW if p.suffix == ".gz" else ArtifactKind.DERIVED,
            )
            for p in sorted(out.rglob("*"))
            if p.is_file()
            and p.name not in ("manifest.json", "g11_run.log")
            and "fault_injection" not in p.parts
        ]

    entries = manifest_entries()
    by_path = {e.path: e for e in entries}

    def evidence_for(pid: str) -> dict[str, list[CaseEvidence]]:
        ev = {}
        for s in SUITES:
            ev[s] = [
                CaseEvidence(
                    scenario_id=sc.scenario_id,
                    result=r,
                    artifact_ok=verify_entry(by_path[tp.relative_to(out).as_posix()], root=out),
                )
                for sc, r, tp in results[pid][s]
            ]
        return ev

    # ---- 4. candidates and decisions -------------------------------------------------
    seeds = SeedLists(
        nominal=P.seeds.nominal,
        regression=sorted({t.scenario.seed for t in regressions}),
        held_out=P.seeds.held_out,
    )
    decisions = {}
    for pid in policies:
        cand = ReleaseCandidate(
            candidate_id=f"rc-{pid}-{sha[:7]}",
            policy_ref=pid,
            sim_name=adapter.sim_name,
            sim_version=adapter.sim_version,
            test_suite_ref=suite.ref,
            seed_lists=seeds,
            commit_sha=sha,
        )
        (out / f"candidate_{pid}.json").write_text(cand.model_dump_json(indent=2))
        d = decide(cand, suite, evidence_for(pid), decided_at=datetime.now(UTC))
        (out / f"release_{pid}.json").write_text(d.model_dump_json(indent=2))
        decisions[pid] = d
        print(f"RELEASE {pid}: {d.status.value}")
        for reason in d.blocking_reasons:
            print("   -", reason)

    # ---- 5. fault injection against the v1 evidence ----------------------------------
    faults_dir = out / "fault_injection"
    faults_dir.mkdir(exist_ok=True)
    base_cand = ReleaseCandidate.model_validate_json(
        (out / f"candidate_{v1.POLICY_ID}.json").read_text()
    )
    faults = []

    def record(name: str, expected: ReleaseStatus, cand, ev, note: str):
        d = decide(cand, suite, ev, decided_at=datetime.now(UTC))
        (faults_dir / f"{name}.release.json").write_text(d.model_dump_json(indent=2))
        row = {
            "fault": name,
            "injected": note,
            "status": d.status.value,
            "expected": expected.value,
            "as_expected": d.status is expected,
            "never_eligible": d.status is not ReleaseStatus.ELIGIBLE,
            "first_reason": d.blocking_reasons[0] if d.blocking_reasons else "",
        }
        faults.append(row)
        print(f"fault {name:24s} -> {d.status.value:10s} (expected {expected.value})")

    ev = evidence_for(v1.POLICY_ID)
    record(
        "known_safety_violation",
        ReleaseStatus.BLOCKED,
        base_cand,
        ev,
        "the real v1 evidence: stored regression tests fail",
    )

    ev = evidence_for(v1.POLICY_ID)
    ev["held_out"] = [e for e in ev["held_out"] if e.scenario_id != "heldout-004"]
    record(
        "missing_heldout_case",
        ReleaseStatus.ERROR
        if decisions[v1.POLICY_ID].status is ReleaseStatus.ERROR
        else ReleaseStatus.BLOCKED,
        base_cand,
        ev,
        "heldout-004 result removed (v1 is also BLOCKED, which outranks INCOMPLETE)",
    )

    # the same missing case on a hypothetical all-green record must be INCOMPLETE
    ev = evidence_for(v1.POLICY_ID)
    ev["regression"] = [
        e.model_copy(update={"result": revalidated(e.result, status="PASS", violations=[])})
        for e in ev["regression"]
    ]
    ev["held_out"] = [e for e in ev["held_out"] if e.result.status.value == "PASS"][:-1]
    record(
        "missing_case_on_green_record",
        ReleaseStatus.INCOMPLETE,
        base_cand,
        ev,
        "regression statuses forced to PASS, a held-out case removed",
    )

    ev = evidence_for(v1.POLICY_ID)
    sc0, r0, tp0 = results[v1.POLICY_ID]["nominal"][0]
    bad = faults_dir / "corrupt.trajectory.json.gz"
    bad.write_bytes(tp0.read_bytes()[: tp0.stat().st_size // 2])
    corrupt_entry = by_path[tp0.relative_to(out).as_posix()].model_copy(
        update={"path": bad.relative_to(out).as_posix()}
    )
    ev["nominal"][0] = ev["nominal"][0].model_copy(
        update={"artifact_ok": verify_entry(corrupt_entry, root=out), "note": "truncated gzip"}
    )
    record(
        "corrupt_artifact",
        ReleaseStatus.ERROR,
        base_cand,
        ev,
        "nominal-s0 trajectory truncated to half its bytes; checksum mismatch",
    )

    ev = evidence_for(v1.POLICY_ID)
    stale = base_cand.model_copy(update={"policy_ref": "push-dls-ik-v0"})
    record(
        "stale_policy_hash",
        ReleaseStatus.ERROR,
        stale,
        ev,
        "candidate names push-dls-ik-v0, results were produced by push-dls-ik-v1",
    )

    ev = evidence_for(v1.POLICY_ID)
    e0 = ev["held_out"][0]
    ev["held_out"][0] = e0.model_copy(
        update={
            "result": O.exec_error_result(
                episode_id=e0.result.episode_id,
                error="simulated: job status unknown",
                spec=SPEC,
                scenario_ref=e0.scenario_id,
                policy_ref=v1.POLICY_ID,
            )
        }
    )
    record(
        "failed_job",
        ReleaseStatus.ERROR,
        base_cand,
        ev,
        "heldout-000 replaced by an EXEC_ERROR (job status unknown)",
    )

    ev = evidence_for(v1.POLICY_ID)
    traj = json.loads(gzip.open(tp0, "rt").read())
    traj["steps"] = traj["steps"][:100]
    cut = faults_dir / "truncated_recording.json"
    cut.write_text(json.dumps(traj))
    rt = O.evaluate_file(
        cut,
        SPEC,
        target_xy=TARGET_XY_M,
        distance_from_nominal=0.0,
        scenario_ref=sc0.scenario_id,
        policy_ref=v1.POLICY_ID,
    )
    ev["nominal"][0] = ev["nominal"][0].model_copy(update={"result": rt})
    record(
        "truncated_recording",
        ReleaseStatus.ERROR
        if decisions[v1.POLICY_ID].status is ReleaseStatus.ERROR
        else ReleaseStatus.BLOCKED,
        base_cand,
        ev,
        f"nominal-s0 recording cut at step 100 -> oracle {rt.status.value}; v1 regressions "
        "still fail so BLOCKED outranks INCOMPLETE",
    )

    ev = evidence_for(v1.POLICY_ID)
    reg_path = out / v1.POLICY_ID / "regression" / f"{regressions[0].test_id}.result.json"
    tampered = json.loads(reg_path.read_text())
    tampered["status"] = "PASS"  # violations left in place: the schema must refuse this
    try:
        EpisodeResult.model_validate(tampered)
        schema_refused = False
        ev["regression"][0] = ev["regression"][0].model_copy(
            update={"result": EpisodeResult.model_validate(tampered)}
        )
    except ValidationError as exc:
        schema_refused = True
        ev["regression"][0] = CaseEvidence(
            scenario_id=regressions[0].test_id,
            result=None,
            artifact_ok=False,
            note=str(exc).splitlines()[0],
        )
    record(
        "injected_pass_verdict",
        ReleaseStatus.ERROR,
        base_cand,
        ev,
        f"regression result status edited to PASS with violations kept; schema refused: "
        f"{schema_refused}",
    )

    ev = evidence_for(v1.POLICY_ID)
    ev["nominal"][0] = ev["nominal"][0].model_copy(
        update={"result": revalidated(ev["nominal"][0].result, spec_ref="push-block-v0")}
    )
    record(
        "spec_mismatch",
        ReleaseStatus.ERROR,
        base_cand,
        ev,
        "nominal-s0 result claims spec push-block-v0",
    )

    all_closed = all(f["as_expected"] and f["never_eligible"] for f in faults)
    (out / "fault_injection.json").write_text(
        json.dumps({"all_fail_closed": all_closed, "cases": faults}, indent=2)
    )
    print("faults fail closed:", all_closed)

    # ---- 6. one video: the repaired policy on the minimized regression test ---------
    video = None
    if not args.no_video:
        sc = regressions[0].scenario
        vpath = out / f"{v2.POLICY_ID}_on_{sc.scenario_id}.mp4"
        r, _ = run_case(v2.POLICY_ID, "video", sc, video=vpath)
        video = {
            "path": vpath.name,
            "policy": v2.POLICY_ID,
            "scenario": sc.scenario_id,
            "status": r.status.value,
        }
        entries = manifest_entries()

    man = ArtifactManifest(
        manifest_id="g11-evidence",
        correlation_id=f"g11-{sha[:12]}",
        created_at=datetime.now(UTC),
        entries=entries,
    )
    (out / "manifest.json").write_text(man.model_dump_json(indent=2))

    # ---- 7. report -------------------------------------------------------------------
    def table(pid):
        return {s: {sc.scenario_id: r.status.value for sc, r, _ in results[pid][s]} for s in SUITES}

    report = {
        "gate": "G11",
        "commit_sha": sha,
        "protocol_sha256": P.digest(),
        "spec_sha256": SPEC.digest(),
        "suite_ref": suite.ref,
        "policies": {
            pid: {
                "source_sha256": registry.get(pid).source_sha256,
                "kind": registry.get(pid).kind.value,
            }
            for pid in policies
        },
        "results": {pid: table(pid) for pid in policies},
        "decisions": {
            pid: {"status": d.status.value, "reasons": d.blocking_reasons}
            for pid, d in decisions.items()
        },
        "repair_attempt": {
            "policy": v2.POLICY_ID,
            "change": "vertical speed capped at 0.05 m/s below 6 cm; push height 3.0 cm",
            "verdict": decisions[v2.POLICY_ID].status.value,
        },
        "fault_injection_all_fail_closed": all_closed,
        "video": video,
        "artifact_count": len(entries),
        "written_utc": datetime.now(UTC).isoformat(),
    }
    (out / "g11_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    v1_blocked = decisions[v1.POLICY_ID].status is ReleaseStatus.BLOCKED
    return 0 if all_closed and v1_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
