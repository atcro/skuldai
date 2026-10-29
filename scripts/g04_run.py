"""G04: one real Nemotron call through the pinned npa CLI, typed in and typed out.

Phase `propose` (npa venv, network):
  1. writes prompts.jsonl (constraint extraction over the G08 Tavily snippets, then a
     hypothesis over the approved domain) in the DOC-VERIFIED {"id","prompt"} format;
  2. runs `npa workbench token-factory generate --model <id> ...` with the flags from the
     installed --help (evidence/G04/npa-token-factory-help.txt); --model is REQUIRED here,
     chosen by a human from the catalog listing (no default model is ever used);
  3. stores the raw generations JSONL (redacted) as the runtime artifact, then validates
     both completions; a rejected completion is recorded, never patched.

Phase `execute` (sim venv): with --approved-by, approves the Nemotron-proposed constraint
(human step), checks the domain, builds the scenario from the Nemotron hypothesis, runs it
and judges it with the oracle. Same chain as G08, with the model in the extractor/author
role and labelled with its real model id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from skuld.core.domains import PUSH_V1
from skuld.core.protocol import PROTOCOL_V1
from skuld.core.schemas import DocumentedConstraint, Hypothesis
from skuld.integrations.tavily import constraints as C
from skuld.integrations.tavily.search import TavilySearchRecord
from skuld.integrations.token_factory import hypotheses as H

CONSTRAINT_ID = "panda-payload-kg-nemotron"


def redact(text: str) -> str:
    key = (os.environ.get("NEBIUS_TOKEN_FACTORY_KEY") or "").strip()
    if key:
        text = text.replace(key, "<redacted>")
    return re.sub(r"Bearer\s+\S+", "Bearer <redacted>", text)


def baseline_facts(g07: Path, g10: Path) -> str:
    m = json.loads((g07 / "metrics.json").read_text())
    g = json.loads((g10 / "g10_report.json").read_text())
    mini = g["minimization"]["minimized"]
    return (
        f"- random baseline: {m['valid_failures_within_budget']} of {m['budget_n_random']} "
        f"episodes were SAFETY_FAIL (finger touched the floor); first at episode "
        f"{m['episodes_to_first_valid_failure']}; all failures had observation_delay_ms >= 152.\n"
        f"- minimized counterexample: observation_delay_ms={mini['observation_delay_ms']:.1f} "
        "with every other variable nominal still fails; reverting delay to 0 passes.\n"
        "- nominal runs (all variables nominal) pass."
    )


def propose(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not args.model:
        print(
            "refusing: --model is required; pick an nvidia/* id from models_list.json",
            file=sys.stderr,
        )
        return 2
    if not args.model.lower().startswith("nvidia/"):
        print(f"refusing: {args.model} is not an NVIDIA model (hackathon rule R3)", file=sys.stderr)
        return 2
    if shutil.which("npa") is None:
        print("refusing: npa not on PATH (activate ~/.venvs/npa)", file=sys.stderr)
        return 2
    rec = TavilySearchRecord.model_validate_json(
        (Path(args.g08) / "tavily_search.json").read_text(encoding="utf-8")
    )
    approved_g08 = DocumentedConstraint.model_validate_json(
        (Path(args.g08) / "constraints" / "approved" / "panda-payload-kg.json").read_text()
    )
    prompts = [
        {
            "id": "constraint",
            "prompt": H.constraint_prompt(rec, property_name="object_mass_kg", unit="kg"),
        },
        {
            "id": "hypothesis",
            "prompt": H.hypothesis_prompt(
                PUSH_V1,
                baseline_facts=baseline_facts(Path(args.g07), Path(args.g10)),
                constraint=approved_g08,
            ),
        },
    ]
    pin = out / "prompts.jsonl"
    pin.write_text("".join(json.dumps(p) + "\n" for p in prompts), encoding="utf-8")
    gens = out / "generations.jsonl"
    cmd = [
        "npa",
        "workbench",
        "token-factory",
        "generate",
        "--input-path",
        str(pin),
        "--output-path",
        str(gens),
        "--model",
        args.model,
        "--system-prompt",
        H.SYSTEM_PROMPT,
        "--temperature",
        "0",
        "--max-tokens",
        str(args.max_tokens),
        "--output",
        "json",
    ]
    print(
        "running:",
        " ".join(cmd[:4]),
        f"--model {args.model} --temperature 0 --max-tokens {args.max_tokens}",
    )
    t0 = time.perf_counter()
    started = datetime.now(UTC)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    wall = time.perf_counter() - t0
    call = {
        "cli": "npa workbench token-factory generate",
        "npa_pin": (out / "npa-pin.txt").read_text() if (out / "npa-pin.txt").exists() else None,
        "model": args.model,
        "temperature": 0,
        "max_tokens": args.max_tokens,
        "prompts": [p["id"] for p in prompts],
        "started_utc": started.isoformat(),
        "wallclock_s": round(wall, 2),
        "exit_code": proc.returncode,
        "stdout": redact(proc.stdout[-4000:]),
        "stderr": redact(proc.stderr[-4000:]),
    }
    if proc.returncode != 0 or not gens.exists():
        call["outcome"] = "FAILED: no generations artifact; nothing is claimed"
        (out / "generate_call.json").write_text(json.dumps(call, indent=2))
        print(json.dumps(call, indent=2))
        return 1
    raw = gens.read_text(encoding="utf-8")
    gens.write_text(redact(raw), encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    call["generations_rows"] = len(rows)
    call["generations_sha256"] = hashlib.sha256(redact(raw).encode()).hexdigest()
    call["generation_keys"] = sorted({k for r in rows for k in r})

    def completion_of(row: dict) -> str:
        for k in ("completion", "output", "generation", "response", "text", "content"):
            if isinstance(row.get(k), str):
                return row[k]
        for k in ("choices", "message"):
            v = row.get(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                msg = v[0].get("message") or v[0]
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
            if isinstance(v, dict) and isinstance(v.get("content"), str):
                return v["content"]
        return ""

    by_id = {}
    for r in rows:
        rid = r.get("id") or r.get("prompt_id") or r.get("input_id")
        by_id[rid] = r
    nonempty = {rid: bool(completion_of(r).strip()) for rid, r in by_id.items()}
    call["nonempty_completion"] = nonempty
    request_ids = {rid: r.get("request_id") or r.get("id") for rid, r in by_id.items()}
    validation = {}

    c_text = completion_of(by_id.get("constraint", {}))
    try:
        c = H.constraint_from_completion(
            c_text,
            record=rec,
            constraint_id=CONSTRAINT_ID,
            property_name="object_mass_kg",
            unit="kg",
        )
        d = out / "constraints" / "proposed"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{CONSTRAINT_ID}.json").write_text(c.model_dump_json(indent=2))
        validation["constraint"] = {
            "accepted": True,
            "value": c.value,
            "unit": c.unit,
            "source_url": str(c.source_url),
            "confidence": c.extraction_confidence,
        }
    except Exception as e:  # noqa: BLE001 - every rejection reason is recorded, none is patched
        validation["constraint"] = {
            "accepted": False,
            "reason": H.describe_rejection(e),
            "completion_head": c_text[:300],
        }

    h_text = completion_of(by_id.get("hypothesis", {}))
    try:
        h = H.hypothesis_from_completion(
            h_text,
            domain=PUSH_V1,
            constraint=approved_g08,
            model_id=args.model,
            request_id=str(
                request_ids.get("hypothesis") or f"gen-{call['generations_sha256'][:12]}"
            ),
        )
        (out / "hypothesis_nemotron.json").write_text(h.model_dump_json(indent=2))
        validation["hypothesis"] = {
            "accepted": True,
            "variables": [v.model_dump() for v in h.variables],
            "hypothesis": h.hypothesis,
        }
    except Exception as e:  # noqa: BLE001
        validation["hypothesis"] = {
            "accepted": False,
            "reason": H.describe_rejection(e),
            "completion_head": h_text[:300],
        }

    call["validation"] = validation
    call["outcome"] = (
        "EXECUTED: nonempty completion(s) from the model id above, captured to generations.jsonl"
        if any(nonempty.values())
        else "FAILED: empty completions; nothing is claimed"
    )
    (out / "generate_call.json").write_text(json.dumps(call, indent=2))
    print(
        json.dumps(
            {
                k: call[k]
                for k in (
                    "model",
                    "exit_code",
                    "wallclock_s",
                    "nonempty_completion",
                    "validation",
                    "outcome",
                )
            },
            indent=2,
        )
    )
    return 0 if any(nonempty.values()) else 1


def execute(args) -> int:
    out = Path(args.out)
    prop = out / "constraints" / "proposed" / f"{CONSTRAINT_ID}.json"
    if not prop.exists() or not (out / "hypothesis_nemotron.json").exists():
        print("nothing accepted to execute (see generate_call.json)", file=sys.stderr)
        return 1
    c = DocumentedConstraint.model_validate_json(prop.read_text())
    a = C.approve_constraint(c, args.approved_by)
    d = out / "constraints" / "approved"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{CONSTRAINT_ID}.json").write_text(a.model_dump_json(indent=2))
    chk = C.check_domain(PUSH_V1, a)
    (out / "domain_check.json").write_text(json.dumps(chk, indent=2))
    print("domain check:", json.dumps(chk))
    h = Hypothesis.model_validate_json((out / "hypothesis_nemotron.json").read_text())
    h.check_against(PUSH_V1)
    sc = C.scenario_from_hypothesis(h, PUSH_V1, scenario_id="g04-nemotron-corner", seed=0)
    (out / "scenario.json").write_text(sc.model_dump_json(indent=2))

    from skuld.oracle import evaluate as O
    from skuld.oracle.specs import PUSH_SPEC_V1, TARGET_XY_M
    from skuld.policies.push_controller import POLICY_ID, PushController
    from skuld.sim.episode import run_episode
    from skuld.sim.mujoco_adapter import MuJoCoPushAdapter

    adapter = MuJoCoPushAdapter(args.menagerie, render=False)
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
        artifact_uris=["scenario.trajectory.json", "hypothesis_nemotron.json"],
    )
    (out / "scenario.result.json").write_text(r.model_dump_json(indent=2))
    print(f"executed: {r.status.value} {[v.rule for v in r.violations]} wall={wall:.1f}s")
    report = {
        "gate": "G04",
        "protocol_sha256": PROTOCOL_V1.digest(),
        "model_id": h.model_id,
        "constraint": {
            "value": a.value,
            "unit": a.unit,
            "source_url": str(a.source_url),
            "approved_by": a.authorizer,
            "approved_at": a.approved_at.isoformat(),
        },
        "domain_check": chk,
        "hypothesis": h.model_dump(mode="json"),
        "scenario": sc.model_dump(mode="json"),
        "verdict": r.status.value,
        "violations": [v.rule for v in r.violations],
        "hypothesis_confirmed_on_this_scenario": r.status.value == "SAFETY_FAIL",
        "written_utc": datetime.now(UTC).isoformat(),
    }
    (out / "g04_report.json").write_text(json.dumps(report, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--out", default="evidence/G04")
    p.add_argument("--g07", default="evidence/G07")
    p.add_argument("--g08", default="evidence/G08")
    p.add_argument("--g10", default="evidence/G10")
    p.add_argument("--model", default=None)
    p.add_argument("--max-tokens", type=int, default=600)
    p.set_defaults(fn=propose)
    e = sub.add_parser("execute")
    e.add_argument("--out", default="evidence/G04")
    e.add_argument("--approved-by", required=True)
    e.add_argument("--menagerie", required=True)
    e.set_defaults(fn=execute)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
