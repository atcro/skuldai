from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from skuld.artifacts.hashing import entry_for_file, sha256_bytes, sha256_file, verify_entry
from skuld.core.schemas import ArtifactEntry, ArtifactKind, ArtifactManifest

EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_of_empty_input_is_the_known_digest(tmp_path: Path) -> None:
    assert sha256_bytes(b"") == EMPTY_SHA
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    assert sha256_file(f) == EMPTY_SHA


def test_entry_round_trips_and_detects_tampering(tmp_path: Path) -> None:
    f = tmp_path / "runs" / "traj.json"
    f.parent.mkdir()
    f.write_text('{"hello": "world"}')
    entry = entry_for_file(f, root=tmp_path, producer="test", kind=ArtifactKind.RAW)
    assert entry.path == "runs/traj.json"
    assert verify_entry(entry, root=tmp_path)
    f.write_text('{"hello": "tampered"}')
    assert not verify_entry(entry, root=tmp_path)
    f.unlink()
    assert not verify_entry(entry, root=tmp_path)


def test_manifest_rejects_bad_digest_and_duplicate_paths() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        ArtifactEntry(path="a", sha256="not-a-digest", size_bytes=1, producer="t", kind="raw")
    good = ArtifactEntry(path="a", sha256=EMPTY_SHA, size_bytes=0, producer="t", kind="raw")
    with pytest.raises(ValidationError, match="duplicate"):
        ArtifactManifest(
            manifest_id="m",
            correlation_id="c",
            created_at=datetime(2026, 10, 26, tzinfo=UTC),
            entries=[good, good],
        )
