"""G08 evidence run: live Tavily search -> proposed DocumentedConstraint ->
(human approval) -> domain check -> Hypothesis -> one executed scenario judged
by the oracle. Two phases so the approval is a real human step:

  phase 1 (default):        search, propose; writes evidence/G08/constraints/proposed/
  phase 2 (--approved-by):  re-reads the proposed constraint, approves it under
                            the given name, checks the domain, builds the
                            hypothesis, runs and judges the scenario.

Needs TAVILY_API_KEY in the environment (phase 1) and the sim venv (phase 2).
The key is never written to any file.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from skuld.core.domains import PUSH_V1
from skuld.core.protocol import PROTOCOL_V1
from skuld.core.schemas import DocumentedConstraint
from skuld.integrations.tavily import constraints as C
from skuld.integrations.tavily.search import TavilySearchRecord, live_search

QUERY = "Franka Emika Panda robot arm payload kg technical specification"
PREFER = ("franka.de", "frankaemika.github.io", "frankarobotics.com")
CONSTRAINT_ID = "panda-payload-kg"


def phase1(out: Path) -> int:
    rec = live_search(QUERY, search_depth="basic", max_results=5)
    (out / "tavily_search.json").write_text(rec.model_dump_json(indent=2))
    print(
        f"tavily: status={rec.status} results={rec.result_count} request_id={rec.request_id} "
        f"response_time={rec.response_time_s}s"
    )
    for h in rec.results:
        print("  ", h.score, h.url)
    if rec.status != "ok":
        print("no usable results; G08 cannot proceed", file=sys.stderr)
        return 1
    prop = C.propose_payload_constraint(rec, constraint_id=CONSTRAINT_ID, prefer_domains=PREFER)
    if prop is None:
        print("no snippet yielded a payload figure; constraint not proposed", file=sys.stderr)
        return 1
    c, hit = prop
    d = out / "constraints" / "proposed"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{c.constraint_id}.json").write_text(c.model_dump_json(indent=2))
    print(f"proposed {c.constraint_id}: {c.property} <= {c.value} {c.unit} from {c.source_url}")
    print('awaiting human approval: re-run with --approved-by "<name>"')
    return 0


def phase2(out: Path, approved_by: str, menagerie: str | None) -> int:
    rec = TavilySearchRecord.model_validate_json((out / "tavily_search.json").read_text())
    c = DocumentedConstraint.model_validate_json(
        (out / "constraints" / "proposed" / f"{CONSTRAINT_ID}.json").read_text()
    )
    a = C.approve_constraint(c, approved_by)
    d = out / "constraints" / "approved"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{a.constraint_id}.json").write_text(a.model_dump_json(indent=2))
    chk = C.check_domain(PUSH_V1, a)
    (out / "domain_check.json").write_text(json.dumps(chk, indent=2))
    print("domain check:", json.dumps(chk))

    author = f"human:{approved_by} (Nemotron authoring pending G04)"
    h = C.hypothesis_from_constraint(PUSH_V1, a, rec, author=author)
    (out / "hypothesis.json").write_text(h.model_dump_json(indent=2))
    sc = C.scenario_from_hypothesis(h, PUSH_V1, scenario_id="g08-hypothesis-corner", seed=0)
    (out / "scenario.json").write_text(sc.model_dump_json(indent=2))
    print("scenario:", sc.values)

    if menagerie is None:
        print("no --menagerie: scenario built but not executed", file=sys.stderr)
        return 1
    # executed only now, in the sim venv
    from skuld.oracle import evaluate as O
    from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M
    from skuld.policies.push_controller import POLICY_ID, PushController
    from skuld.sim.episode import run_episode
    from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

    adapter = MuJoCoPushAdapter(menagerie, render=False)
    policy = PushController(adapter.staged.scene_xml)
    t0 = time.perf_counter()
    ep = run_episode(
        adapter, policy, sc, PUSH_V1, policy_ref=POLICY_ID, max_time_s=PUSH_SPEC_V1.deadline_s
    )
    wall = time.perf_counter() - t0
    (out / "scenario.trajectory.json").write_text(ep.trajectory.model_dump_json())
    r = O.evaluate(
        ep.trajectory,
        PUSH_SPEC_V1,
        target_xy=TARGET_XY_M,
        distance_from_nominal=sc.distance_from_nominal(PUSH_V1),
        wallclock_s=wall,
        artifact_uris=["scenario.trajectory.json", "hypothesis.json", str(a.source_url)],
    )
    (out / "scenario.result.json").write_text(r.model_dump_json(indent=2))
    print(f"executed: {r.status.value} {[v.rule for v in r.violations]} wall={wall:.1f}s")

    report = {
        "gate": "G08",
        "tavily": {
            "status": rec.status,
            "request_id": rec.request_id,
            "response_time_s": rec.response_time_s,
            "started_utc": rec.started_utc.isoformat(),
            "result_count": rec.result_count,
            "urls": [str(x.url) for x in rec.results],
        },
        "constraint": {
            "id": a.constraint_id,
            "property": a.property,
            "value": a.value,
            "unit": a.unit,
            "source_url": str(a.source_url),
            "approved_by": a.authorizer,
            "approved_at": a.approved_at.isoformat() if a.approved_at else None,
        },
        "domain_check": chk,
        "protocol_sha256": PROTOCOL_V1.digest(),
        "hypothesis_author": author,
        "scenario": sc.model_dump(mode="json"),
        "verdict": r.status.value,
        "violations": [v.rule for v in r.violations],
        "expected_failure_signature": h.expected_failure_signature,
        "hypothesis_confirmed": r.status.value == "SAFETY_FAIL",
        "written_utc": datetime.now(UTC).isoformat(),
    }
    (out / "g08_report.json").write_text(json.dumps(report, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/G08")
    ap.add_argument("--approved-by", default=None)
    ap.add_argument("--menagerie", default=None)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.approved_by:
        return phase2(out, args.approved_by, args.menagerie)
    return phase1(out)


if __name__ == "__main__":
    raise SystemExit(main())
