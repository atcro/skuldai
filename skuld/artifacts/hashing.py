"""SHA-256 helpers for artifact provenance (spec.md section 6.1, 15).

Raw bytes and files are hashed directly. Models are hashed through their
canonical JSON so two equal contracts always produce the same digest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from skuld.core.schemas import ArtifactEntry, ArtifactKind, SkuldModel

_CHUNK = 1 << 20


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_model(model: SkuldModel) -> str:
    return model.digest()


def entry_for_file(
    path: str | Path,
    *,
    root: str | Path,
    producer: str,
    kind: ArtifactKind,
) -> ArtifactEntry:
    """Build a manifest entry for `path`, recorded relative to `root`."""
    p = Path(path)
    rel = p.resolve().relative_to(Path(root).resolve()).as_posix()
    return ArtifactEntry(
        path=rel,
        sha256=sha256_file(p),
        size_bytes=p.stat().st_size,
        producer=producer,
        kind=kind,
    )


def verify_entry(entry: ArtifactEntry, *, root: str | Path) -> bool:
    """True only if the file exists and both size and digest match."""
    p = Path(root) / entry.path
    if not p.is_file():
        return False
    if p.stat().st_size != entry.size_bytes:
        return False
    return sha256_file(p) == entry.sha256
