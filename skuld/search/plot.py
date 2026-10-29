"""Comparison plot as a dependency-free SVG (spec 8.1: curves vs cumulative episodes).

Two panels: valid failures found, and running minimum distance from nominal,
both against cumulative episodes, one polyline per strategy. Numbers come only
from the ledgers passed in; nothing is smoothed or extrapolated.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from skuld.search.objective import CurvePoint

W, H, PAD = 420, 260, 44
COLORS = ("#6b7280", "#2563eb", "#dc2626", "#059669")


def _panel(
    x_off: int,
    title: str,
    series: dict[str, Sequence[CurvePoint]],
    key: str,
    budget: int,
) -> str:
    ys = [getattr(p, key) for pts in series.values() for p in pts if getattr(p, key) is not None]
    y_max = max(ys) if ys else 1.0
    y_max = y_max if y_max > 0 else 1.0
    if key == "valid_failures_found":
        y_max = max(1, math.ceil(y_max))
    else:
        y_max = math.ceil(y_max * 10) / 10

    def sx(e: float) -> float:
        return x_off + PAD + (W - 2 * PAD) * e / budget

    def sy(v: float) -> float:
        return H - PAD - (H - 2 * PAD) * v / y_max

    out = [
        f'<text x="{x_off + W / 2}" y="18" text-anchor="middle" font-size="12" '
        f'font-weight="600">{title}</text>',
        f'<line x1="{sx(0)}" y1="{sy(0)}" x2="{sx(budget)}" y2="{sy(0)}" stroke="#111"/>',
        f'<line x1="{sx(0)}" y1="{sy(0)}" x2="{sx(0)}" y2="{sy(y_max)}" stroke="#111"/>',
        f'<text x="{sx(budget / 2)}" y="{H - 10}" text-anchor="middle" font-size="10">'
        f"cumulative episodes (budget {budget})</text>",
        f'<text x="{sx(0) - 4}" y="{sy(0) + 3}" text-anchor="end" font-size="9">0</text>',
        f'<text x="{sx(0) - 4}" y="{sy(y_max) + 3}" text-anchor="end" font-size="9">{y_max:g}'
        "</text>",
        f'<text x="{sx(budget)}" y="{sy(0) + 12}" text-anchor="middle" font-size="9">{budget}'
        "</text>",
    ]
    for (label, pts), color in zip(series.items(), COLORS, strict=False):
        coords = [
            (sx(p.cumulative_episodes), sy(getattr(p, key)))
            for p in pts
            if getattr(p, key) is not None
        ]
        if coords:
            d = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
            out.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{d}">'
                f"<title>{label}</title></polyline>"
            )
            x, y = coords[-1]
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
    return "\n".join(out)


def write_comparison_svg(
    path: str | Path, series: dict[str, Sequence[CurvePoint]], *, budget: int, caption: str
) -> None:
    legend = []
    for i, (label, color) in enumerate(zip(series, COLORS, strict=False)):
        y = H + 16 + 14 * i
        legend.append(
            f'<line x1="{PAD}" y1="{y}" x2="{PAD + 24}" y2="{y}" stroke="{color}" '
            f'stroke-width="2"/><text x="{PAD + 30}" y="{y + 4}" font-size="10">{label}</text>'
        )
    total_h = H + 24 + 14 * len(series) + 18
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * W}" height="{total_h}" '
        f'viewBox="0 0 {2 * W} {total_h}" font-family="system-ui, sans-serif">',
        '<rect width="100%" height="100%" fill="white"/>',
        _panel(0, "valid failures found", series, "valid_failures_found", budget),
        _panel(W, "running min distance from nominal", series, "running_min_distance", budget),
        *legend,
        f'<text x="{PAD}" y="{total_h - 6}" font-size="9" fill="#444">{caption}</text>',
        "</svg>",
    ]
    Path(path).write_text("\n".join(svg) + "\n", encoding="utf-8")
