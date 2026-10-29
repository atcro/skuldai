"""Skuld API and dashboard.

GET /health is the G01 liveness check. The four dashboard surfaces (spec 11) are
plain HTML rendered by Jinja from real run records under `evidence/`:

    /            Test Lab            policy, budget, failures, nearest distance, ledger, video
    /atlas       Failure Atlas       observed pass/fail points over two chosen variables
    /counterexample  Counterexample Replay   original vs minimized, removed vs kept, replay
    /release     Release Gate        per-suite results, status, reasons, provenance, faults

Read-only. Nothing is computed here that could change a verdict, and any
missing record is shown as missing rather than filled in.
"""

from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from skuld.api import records as R
from skuld.core.domains import PUSH_V1

SERVICE_NAME = "skuld"
WEB = R.REPO_ROOT / "web"
VARIABLES = [v.name for v in PUSH_V1.variables]


def _package_version() -> str:
    try:
        return version(SERVICE_NAME)
    except PackageNotFoundError:
        return "0.0.0-uninstalled"


app = FastAPI(
    title="Skuld",
    description="Falsification-driven CI/CD for embodied robot policies.",
    version=_package_version(),
)
templates = Jinja2Templates(directory=str(WEB / "templates"))
if (WEB / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB / "static")), name="static")
if R.evidence_root().is_dir():
    app.mount("/evidence", StaticFiles(directory=str(R.evidence_root())), name="evidence")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Carries no claim about simulator, oracle or provider state."""
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": _package_version(),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def _render(request: Request, name: str, rec: R.Records, **ctx) -> HTMLResponse:
    ctx.update(request=request, missing=rec.missing, evidence_root=str(rec.root))
    return templates.TemplateResponse(request, name, ctx)


def _short(h: str | None, n: int = 12) -> str:
    return (h or "")[:n]


# ----------------------------------------------------------------- Test Lab


@app.get("/", response_class=HTMLResponse)
def test_lab(request: Request) -> HTMLResponse:
    rec = R.records()
    policy = rec.load("G10/policy_manifest.json")
    protocol_sha = (
        (rec.root / "G10/protocol_sha256.txt").read_text().strip()
        if rec.exists("G10/protocol_sha256.txt")
        else None
    )
    comparison = rec.load("G10/comparison.json") or {}
    ledger = rec.rows("G10/active_ledger.csv")
    g10 = rec.load("G10/g10_report.json") or {}
    video = None
    for rel in (
        "G10/minimized_failure.mp4",
        "G10/original_failure.mp4",
        "G07/first_random_failure.mp4",
    ):
        if rec.exists(rel):
            video = rel
            break
    return _render(
        request,
        "lab.html",
        rec,
        title="Test Lab",
        policy=policy,
        protocol_sha=protocol_sha,
        comparison=comparison,
        ledger=ledger,
        variables=VARIABLES,
        video=video,
        incumbents=set(g10.get("active_incumbents", [])),
        sim=g10.get("sim"),
        short=_short,
    )


# ------------------------------------------------------------ Failure Atlas


@app.get("/atlas", response_class=HTMLResponse)
def failure_atlas(
    request: Request, x: str = "observation_delay_ms", y: str = "object_mass_kg"
) -> HTMLResponse:
    rec = R.records()
    if x not in VARIABLES or y not in VARIABLES or x == y:
        x, y = "observation_delay_ms", "object_mass_kg"
    eps = rec.episodes(VARIABLES)
    sx, sy = PUSH_V1.spec(x), PUSH_V1.spec(y)
    w, h, pad = 560, 400, 48

    def px(v: float) -> float:
        return pad + (w - 2 * pad) * (v - sx.min) / sx.range

    def py(v: float) -> float:
        return h - pad - (h - 2 * pad) * (v - sy.min) / sy.range

    points = [
        {
            "cx": round(px(e.values[x]), 1),
            "cy": round(py(e.values[y]), 1),
            "e": e,
        }
        for e in eps
    ]
    ce = rec.load("G10/counterexample.json")
    ce_pt = None
    if ce:
        mv = ce["minimized"]["values"]
        ce_pt = {"cx": round(px(mv[x]), 1), "cy": round(py(mv[y]), 1), "values": mv}
    fails = [e for e in eps if e.failed]
    nearest = min(fails, key=lambda e: e.distance) if fails else None
    return _render(
        request,
        "atlas.html",
        rec,
        title="Failure Atlas",
        variables=VARIABLES,
        x=x,
        y=y,
        sx=sx,
        sy=sy,
        w=w,
        h=h,
        pad=pad,
        nominal=(round(px(sx.nominal), 1), round(py(sy.nominal), 1)),
        points=points,
        ce_pt=ce_pt,
        n_total=len(eps),
        n_fail=len(fails),
        nearest=nearest,
        sources=sorted({e.source for e in eps}),
    )


# ------------------------------------------------------ Counterexample Replay


@app.get("/counterexample", response_class=HTMLResponse)
def counterexample(request: Request) -> HTMLResponse:
    rec = R.records()
    ce = rec.load("G10/counterexample.json")
    mins = rec.load("G10/minimization.json")
    g10 = rec.load("G10/g10_report.json") or {}
    ledger = rec.rows("G10/minimize_ledger.csv")
    rows = []
    if ce:
        for v in VARIABLES:
            o, m = ce["original"]["values"][v], ce["minimized"]["values"][v]
            rows.append(
                {
                    "name": v,
                    "unit": PUSH_V1.spec(v).unit,
                    "nominal": PUSH_V1.spec(v).nominal,
                    "original": o,
                    "minimized": m,
                    "removed": v in ce["removed_variables"],
                }
            )
    return _render(
        request,
        "counterexample.html",
        rec,
        title="Counterexample Replay",
        ce=ce,
        rows=rows,
        mins=mins,
        replay=g10.get("replay"),
        videos=g10.get("videos") or {},
        ledger=ledger,
        variables=VARIABLES,
    )


# ------------------------------------------------------------- Release Gate


@app.get("/release", response_class=HTMLResponse)
def release_gate(request: Request) -> HTMLResponse:
    rec = R.records()
    report = rec.load("G11/g11_report.json") or {}
    suite = rec.load("G11/test_suite.json")
    registry = rec.load("G11/policy_registry.json")
    faults = rec.load("G11/fault_injection.json")
    decisions = {}
    candidates = {}
    for pid in report.get("policies") or {}:
        decisions[pid] = rec.load(f"G11/release_{pid}.json")
        candidates[pid] = rec.load(f"G11/candidate_{pid}.json")
    return _render(
        request,
        "release.html",
        rec,
        title="Release Gate",
        report=report,
        suite=suite,
        registry=registry,
        faults=faults,
        decisions=decisions,
        candidates=candidates,
        results=report.get("results") or {},
        short=_short,
    )


def main() -> None:  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["app", "Path"]
