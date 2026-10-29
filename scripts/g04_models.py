"""G04 step 2: list the Token Factory catalog visible to our key. Read-only.

DOC-VERIFIED 2026-10-29 (docs.tokenfactory.nebius.com/api-reference/models/list-models):
GET https://api.tokenfactory.nebius.com/v1/models, bearer auth, optional ?verbose=true
returning id, status, pricing, context_length, supported_features per model. The npa docs
say the equivalent `verify` call "does not test inference or billing access", so this is
not an inference call and is never claimed as one (CLAUDE.md rule 4).

The key is read from the git-ignored .env (NEBIUS_TOKEN_FACTORY_API_KEY). It is never
written to the evidence; error bodies are redacted of any bearer-like token.

Usage (any venv with httpx + python-dotenv):  python scripts/g04_models.py --out evidence/G04
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE = "https://api.tokenfactory.nebius.com/v1/"


def redact(text: str, key: str) -> str:
    text = text.replace(key, "<redacted>")
    return re.sub(r"Bearer\s+\S+", "Bearer <redacted>", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = (os.environ.get("NEBIUS_TOKEN_FACTORY_API_KEY") or "").strip()
    if len(key) < 20:
        print("NEBIUS_TOKEN_FACTORY_API_KEY missing from .env", file=sys.stderr)
        return 2
    base = os.environ.get("NEBIUS_TOKEN_FACTORY_BASE_URL", BASE)
    started = datetime.now(UTC)
    record: dict = {"endpoint": base + "models?verbose=true", "started_utc": started.isoformat()}
    try:
        r = httpx.get(
            base + "models",
            params={"verbose": "true"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=30,
        )
        record["status_code"] = r.status_code
        record["response_time_s"] = round(r.elapsed.total_seconds(), 3)
        record["request_id"] = r.headers.get("x-request-id") or r.headers.get("request-id")
        if r.status_code != 200:
            record["error_body"] = redact(r.text[:2000], key)
            (out / "models_list.json").write_text(json.dumps(record, indent=2))
            print(json.dumps(record, indent=2))
            return 1
        data = r.json()
    except httpx.HTTPError as e:
        record["error"] = redact(f"{type(e).__name__}: {e}", key)
        (out / "models_list.json").write_text(json.dumps(record, indent=2))
        print(json.dumps(record, indent=2))
        return 1

    models = data.get("data", [])
    rows = []
    for m in models:
        rows.append(
            {
                "id": m.get("id"),
                "status": m.get("status"),
                "status_reason": m.get("status_reason"),
                "context_length": m.get("context_length"),
                "pricing": m.get("pricing"),
                "modality": (m.get("architecture") or {}).get("modality"),
                "supported_features": m.get("supported_features"),
            }
        )
    nvidia = [x for x in rows if (x["id"] or "").lower().startswith("nvidia/")]
    record.update(
        {
            "model_count": len(rows),
            "nvidia_models": nvidia,
            "all_model_ids": sorted(x["id"] for x in rows if x["id"]),
            "finished_utc": datetime.now(UTC).isoformat(),
            "note": "catalog listing only; not inference (CLAUDE.md rule 4)",
        }
    )
    (out / "models_list.json").write_text(json.dumps(record, indent=2))
    print(
        f"HTTP {r.status_code} in {record['response_time_s']}s: {len(rows)} models, "
        f"{len(nvidia)} nvidia/*"
    )
    for x in nvidia:
        price = x["pricing"] or {}
        print(
            f"  {x['id']}: status={x['status']} ctx={x['context_length']} "
            f"prompt={price.get('prompt')} completion={price.get('completion')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
