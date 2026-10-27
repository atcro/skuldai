"""Write RGB frames to an H.264 MP4 through an ffmpeg pipe (ffmpeg is in the WSL toolchain)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np


class FfmpegWriter:
    def __init__(self, path: str | Path, width: int, height: int, fps: int = 25) -> None:
        exe = shutil.which("ffmpeg")
        if exe is None:
            raise RuntimeError("ffmpeg not found on PATH")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.width, self.height = width, height
        self.frames = 0
        self._proc = subprocess.Popen(
            [
                exe,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                f"{width}x{height}",
                "-r",
                str(fps),
                "-i",
                "-",
                "-an",
                "-vcodec",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "22",
                "-movflags",
                "+faststart",
                str(self.path),
            ],
            stdin=subprocess.PIPE,
        )

    def write(self, frame: np.ndarray) -> None:
        if frame.shape != (self.height, self.width, 3):
            raise ValueError(f"frame shape {frame.shape} != {(self.height, self.width, 3)}")
        assert self._proc.stdin is not None
        self._proc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        self.frames += 1

    def close(self) -> int:
        if self._proc.stdin is not None:
            self._proc.stdin.close()
        rc = self._proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited with {rc}")
        return self.frames

    def __enter__(self) -> FfmpegWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
