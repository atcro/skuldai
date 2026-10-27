"""G05 step 52/56/57 smoke check: MuJoCo imports, the Panda scene loads, physics
advances, an actuator command changes joint state, and one frame renders
offscreen. Prints JSON evidence to stdout.

Usage: python scripts/mujoco_check.py <path-to-menagerie-checkout> [out.png]
Run with MUJOCO_GL=egl (WSL2 with Mesa) or MUJOCO_GL=osmesa.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    menagerie = Path(argv[1]).resolve()
    out_png = Path(argv[2]).resolve() if len(argv) > 2 else None
    scene = menagerie / "franka_emika_panda" / "scene.xml"
    if not scene.is_file():
        print(f"scene not found: {scene}", file=sys.stderr)
        return 1

    import mujoco
    import numpy as np

    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    # Step with zero control: physics must advance time.
    for _ in range(100):
        mujoco.mj_step(model, data)
    t_after_100 = float(data.time)

    # Prove an actuator command changes joint state (runbook G05 step 56).
    q_before = data.qpos[: model.nu].copy()
    data.ctrl[:] = model.actuator_ctrlrange[:, 1] * 0.5 + model.actuator_ctrlrange[:, 0] * 0.5
    data.ctrl[0] = model.actuator_ctrlrange[0, 1]  # drive joint 1 toward its upper limit
    for _ in range(500):
        mujoco.mj_step(model, data)
    q_after = data.qpos[: model.nu].copy()
    joint1_delta = float(abs(q_after[0] - q_before[0]))

    render = {"attempted": False, "ok": False, "error": None, "gl": os.environ.get("MUJOCO_GL")}
    try:
        render["attempted"] = True
        renderer = mujoco.Renderer(model, height=240, width=320)
        renderer.update_scene(data)
        rgb = renderer.render()
        render["ok"] = bool(rgb.shape == (240, 320, 3) and int(rgb.max()) > 0)
        render["shape"] = list(rgb.shape)
        render["mean_intensity"] = float(rgb.mean())
        if out_png is not None and render["ok"]:
            try:
                from PIL import Image  # optional

                Image.fromarray(rgb).save(out_png)
                render["png"] = str(out_png)
            except ImportError:
                np.save(out_png.with_suffix(".npy"), rgb)
                render["npy"] = str(out_png.with_suffix(".npy"))
        renderer.close()
    except Exception as exc:  # noqa: BLE001 - we want the message in evidence
        render["error"] = f"{type(exc).__name__}: {exc}"

    evidence = {
        "gate": "G05",
        "kind": "mujoco_smoke",
        "mujoco_version": mujoco.__version__,
        "numpy_version": np.__version__,
        "scene": str(scene),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "timestep_s": float(model.opt.timestep),
        "time_after_100_steps_s": t_after_100,
        "joint1_delta_rad_after_command": joint1_delta,
        "actuator_changes_state": joint1_delta > 1e-3,
        "render": render,
    }
    print(json.dumps(evidence, indent=2))
    ok = evidence["actuator_changes_state"] and t_after_100 > 0 and render["ok"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
