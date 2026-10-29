"""Read-only loaders over the evidence folders for the dashboard (spec 11).

Every number the dashboard shows comes from a file written by a gate run and
hashed in that gate's manifest. Nothing here computes a verdict, fits a
boundary or fills a gap: a missing file is reported as missing and the surface
says so on screen. The evidence root is `SKULD_EVIDENCE_DIR` or `<repo>/evidence`.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def evidence_root() -> Path:
    return Path(os.environ.get("SKULD_EVIDENCE_DIR", REPO_ROOT / "evidence"))


def _json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _csv(path: Path) -> list[dict]:
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


@dataclass
class Episode:
    """One stored episode row, from a G07 or G10 ledger CSV."""

    source: str
    scenario_id: str
    values: dict[str, float]
    status: str
    valid_failure: bool
    distance: float
    phase: str = ""
    move: str = ""
    accepted: bool = False

    @property
    def failed(self) -> bool:
        return self.valid_failure


@dataclass
class Records:
    root: Path
    missing: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ helpers
    def load(self, rel: str):
        p = self.root / rel
        data = _json(p)
        if data is None:
            self.missing.append(rel)
        return data

    def rows(self, rel: str) -> list[dict]:
        r = _csv(self.root / rel)
        if not r:
            self.missing.append(rel)
        return r

    def exists(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    # ------------------------------------------------------------ episodes
    def episodes(self, variables: list[str]) -> list[Episode]:
        out: list[Episode] = []
        sources = (
            ("G07 random", "G07/random_baseline.csv"),
            ("G10 active", "G10/active_ledger.csv"),
            ("G10 active + hypothesis", "G10/active_hyp_ledger.csv"),
            ("G10 minimizer", "G10/minimize_ledger.csv"),
        )
        for label, rel in sources:
            for r in self.rows(rel):
                try:
                    out.append(
                        Episode(
                            source=label,
                            scenario_id=r["scenario_id"],
                            values={v: float(r[v]) for v in variables},
                            status=r["status"],
                            valid_failure=r.get("valid_failure") == "True",
                            distance=float(r["distance_from_nominal"]),
                            phase=r.get("phase", ""),
                            move=r.get("move", ""),
                            accepted=r.get("accepted") == "True",
                        )
                    )
                except (KeyError, ValueError):
                    self.missing.append(f"{rel}: unreadable row {r.get('scenario_id')}")
        return out


def records() -> Records:
    return Records(root=evidence_root())
