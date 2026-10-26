"""Skuld API entry point.

G01 acceptance requires GET /health to return 200. Everything else arrives with
later gates. The dashboard surfaces (spec.md section 11) are served from here as
plain HTML via Jinja templates once there are real run records to show.
"""

from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI

SERVICE_NAME = "skuld"


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
