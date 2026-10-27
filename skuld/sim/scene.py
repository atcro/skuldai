"""Push-task scene built on the pinned MuJoCo Menagerie Panda (spec 4.2, 4.3).

The Menagerie `panda.xml` is treated as read-only downloaded data. We stage a
derived copy next to a symlink of its mesh assets, with two edits:

1. its 9-DoF `home` keyframe removed (our scene adds a free block, so nq = 16
   and the original keyframe would fail to compile), and
2. a site named `ee_site` added to the `hand` body at the fingertip pinch point.

The scene itself (floor, block, target, camera, full keyframe) is generated from
the template below. Both staged XML files are hashed into `scene_sha256`.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

PANDA_SUBDIR = "franka_emika_panda"
PANDA_XML = "panda.xml"
STAGED_PANDA_XML = "panda_skuld.xml"
STAGED_SCENE_XML = "push_scene.xml"

# names used by adapter, policy and oracle
EE_SITE = "ee_site"
EE_SITE_OFFSET_M = (0.0, 0.0, 0.1034)  # hand frame -> fingertip pinch point
HAND_BODY = "hand"
BLOCK_BODY = "block"
BLOCK_GEOM = "block_geom"
BLOCK_JOINT = "block_free"
FLOOR_GEOM = "floor"
TARGET_SITE = "target"
CAMERA = "demo"
KEYFRAME = "home"
ARM_JOINTS = tuple(f"joint{i}" for i in range(1, 8))
FINGER_JOINTS = ("finger_joint1", "finger_joint2")
ARM_ACTUATORS = tuple(f"actuator{i}" for i in range(1, 8))
GRIPPER_ACTUATOR = "actuator8"
ROBOT_LINK_BODIES = frozenset({f"link{i}" for i in range(8)} | {HAND_BODY})
FINGER_BODIES = frozenset({"left_finger", "right_finger"})
WORLD_BODY = "world"

# nominal geometry (SI)
BLOCK_HALF_M = 0.02
BLOCK_START_M = (0.45, -0.15, BLOCK_HALF_M)
TARGET_POS_M = (0.45, 0.15, 0.001)
TARGET_RADIUS_M = 0.04
NOMINAL_BLOCK_MASS_KG = 0.1
NOMINAL_FRICTION = 0.6
HOME_QPOS_ARM = (0.0, 0.0, 0.0, -1.57079, 0.0, 1.57079, -0.7853, 0.04, 0.04)
HOME_CTRL_ARM = (0.0, 0.0, 0.0, -1.57079, 0.0, 1.57079, -0.7853)
GRIPPER_CTRL_OPEN = 255.0
GRIPPER_CTRL_CLOSED = 0.0

_SCENE_TEMPLATE = """<mujoco model="skuld push scene">
  <include file="{panda_xml}"/>

  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3" specular="0 0 0"/>
    <rgba haze="0.15 0.25 0.35 1"/>
    <global azimuth="120" elevation="-20" offwidth="1280" offheight="720"/>
  </visual>

  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
  </asset>

  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1" directional="true"/>
    <geom name="{floor}" size="0 0 0.05" type="plane" material="groundplane"
      friction="{friction} 0.005 0.0001"/>
    <body name="{block}" pos="{bx} {by} {bz}">
      <freejoint name="{block_joint}"/>
      <geom name="{block_geom}" type="box" size="{half} {half} {half}" mass="{mass}"
        rgba="0.9 0.35 0.1 1" friction="{friction} 0.005 0.0001"/>
    </body>
    <site name="{target}" type="cylinder" pos="{tx} {ty} {tz}" size="{radius} 0.001"
      rgba="0.1 0.8 0.2 0.45"/>
    <camera name="{camera}" pos="1.45 -1.15 0.75" xyaxes="0.62 0.78 0 -0.28 0.22 0.93" fovy="42"/>
  </worldbody>

  <keyframe>
    <key name="{keyframe}" qpos="{home_qpos} {bx} {by} {bz} 1 0 0 0" ctrl="{home_ctrl} {grip_open}"/>
  </keyframe>
</mujoco>
"""


@dataclass(frozen=True)
class StagedScene:
    scene_xml: Path
    panda_xml: Path
    assets_dir: Path
    scene_sha256: str
    menagerie_dir: Path


def _derive_panda_xml(src: Path) -> str:
    tree = ET.parse(src)
    root = tree.getroot()
    for kf in root.findall("keyframe"):
        root.remove(kf)
    hand = next((b for b in root.iter("body") if b.get("name") == HAND_BODY), None)
    if hand is None:
        raise RuntimeError(f"no body named {HAND_BODY!r} in {src}")
    if not any(s.get("name") == EE_SITE for s in hand.findall("site")):
        ET.SubElement(
            hand,
            "site",
            {
                "name": EE_SITE,
                "pos": " ".join(f"{v:g}" for v in EE_SITE_OFFSET_M),
                "size": "0.005",
                "rgba": "1 0 0 0.6",
            },
        )
    return ET.tostring(root, encoding="unicode")


def render_scene_xml() -> str:
    return _SCENE_TEMPLATE.format(
        panda_xml=STAGED_PANDA_XML,
        floor=FLOOR_GEOM,
        friction=NOMINAL_FRICTION,
        block=BLOCK_BODY,
        block_joint=BLOCK_JOINT,
        block_geom=BLOCK_GEOM,
        bx=BLOCK_START_M[0],
        by=BLOCK_START_M[1],
        bz=BLOCK_START_M[2],
        half=BLOCK_HALF_M,
        mass=NOMINAL_BLOCK_MASS_KG,
        target=TARGET_SITE,
        tx=TARGET_POS_M[0],
        ty=TARGET_POS_M[1],
        tz=TARGET_POS_M[2],
        radius=TARGET_RADIUS_M,
        camera=CAMERA,
        keyframe=KEYFRAME,
        home_qpos=" ".join(f"{v:g}" for v in HOME_QPOS_ARM),
        home_ctrl=" ".join(f"{v:g}" for v in HOME_CTRL_ARM),
        grip_open=f"{GRIPPER_CTRL_OPEN:g}",
    )


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "skuld" / "scene"


def stage_scene(menagerie_dir: str | Path, cache_dir: str | Path | None = None) -> StagedScene:
    """Create (idempotently) the staged scene directory and return its paths and hash."""
    menagerie = Path(menagerie_dir).resolve()
    src_dir = menagerie / PANDA_SUBDIR
    src_xml = src_dir / PANDA_XML
    src_assets = src_dir / "assets"
    if not src_xml.is_file() or not src_assets.is_dir():
        raise FileNotFoundError(f"expected {PANDA_XML} and assets/ under {src_dir}")

    out = Path(cache_dir) if cache_dir else default_cache_dir()
    out.mkdir(parents=True, exist_ok=True)

    panda_text = _derive_panda_xml(src_xml)
    scene_text = render_scene_xml()
    (out / STAGED_PANDA_XML).write_text(panda_text, encoding="utf-8")
    (out / STAGED_SCENE_XML).write_text(scene_text, encoding="utf-8")

    assets_link = out / "assets"
    if assets_link.is_symlink() or assets_link.exists():
        if assets_link.is_symlink() and assets_link.resolve() == src_assets.resolve():
            pass
        else:
            if assets_link.is_dir() and not assets_link.is_symlink():
                shutil.rmtree(assets_link)
            else:
                assets_link.unlink()
            assets_link.symlink_to(src_assets, target_is_directory=True)
    else:
        try:
            assets_link.symlink_to(src_assets, target_is_directory=True)
        except OSError:
            shutil.copytree(src_assets, assets_link)

    digest = hashlib.sha256()
    digest.update(panda_text.encode("utf-8"))
    digest.update(b"\n--\n")
    digest.update(scene_text.encode("utf-8"))
    return StagedScene(
        scene_xml=out / STAGED_SCENE_XML,
        panda_xml=out / STAGED_PANDA_XML,
        assets_dir=assets_link,
        scene_sha256=digest.hexdigest(),
        menagerie_dir=menagerie,
    )
