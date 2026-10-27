# G05 | Real MuJoCo simulation + observable control

```yaml
schema_version: skuld.gate-report.v1
gate: G05
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5, Python 3.12.3, venv ~/.venvs/skuld-mujoco (mujoco 3.17.0, numpy 2.5.4, see evidence/G05/requirements.sim.freeze.txt), headless EGL rendering via Mesa, ffmpeg 6.1.1; MuJoCo Menagerie franka_emika_panda @ f3b6013629c7b94f8ee93fd977b161fa8350f9bc (Apache-2.0)'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g05_setup.sh'   # sim venv, sparse Menagerie clone, EGL smoke
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g05_run.sh'     # ruff, pytest (sim venv), scripts/g05_run.py
evidence_paths:
  - evidence/G05/menagerie-pin.txt
  - evidence/G05/panda-model-LICENSE.txt
  - evidence/G05/mujoco-smoke-egl.json
  - evidence/G05/panda-frame.png
  - evidence/G05/requirements.sim.freeze.txt
  - evidence/G05/tests-sim-venv.txt
  - evidence/G05/g05_run.log
  - evidence/G05/g05_run_report.json          # per-episode summary, replay comparison, hashes
  - evidence/G05/policy_manifest.json         # policy_id push-dls-ik-v1, kind classical, source sha256
  - evidence/G05/domain_push_v1.json          # the 4-variable perturbation domain (PROPOSED until G07)
  - evidence/G05/scene_sha256.txt
  - evidence/G05/<episode>.trajectory.json    # 10 per-step trajectories (nominal, nominal_replay, 8 perturbed)
  - evidence/G05/<episode>.mp4                # 9 rendered episodes, 640x480 @ 25 fps, from the simulator camera
provider_run_ids: []
actual_test_results:
  - 'ruff check .: All checks passed (exit 0)'
  - 'python -m pytest -q -ra (sim venv): 44 passed in 1.72s (35 from G02 + 9 MuJoCo adapter tests), exit 0'
  - 'scripts/g05_run.py: 10 episodes ran, exit 0; see table below'
spend_approved: false
approved_by: null
blockers: []
next_action: 'G06: deterministic oracle over the saved trajectories (goal, forbidden-contact, timeout, invalid telemetry) producing EpisodeResult; it decides whether delay_200 and combo are SAFETY_FAIL. Then G07 random baseline, unrendered.'
```

## What ran (EXECUTED 2026-10-26, all local, no spend)

Closed loop at 50 Hz control over 2 ms physics substeps (10 substeps per control
step). Each control step: `policy.act(observation)` -> `adapter.act(action)` ->
`adapter.step()` -> `adapter.observe()`. The policy recomputes its action from
the observation every step; nothing is pre-recorded.

| Episode | Scenario (deviation from nominal) | Goal reached (provisional) | Time to goal (s) | Final block-to-target (m) | Forbidden-contact steps | Steps | Video |
|---|---|---|---|---|---|---|---|
| nominal | none | yes | 6.68 | 0.006 | 0 | 360 | nominal.mp4 |
| nominal_replay | none (same seed, same scenario) | yes | 6.68 | 0.006 | 0 | 360 | none (replay check only) |
| heavy | object_mass_kg 0.5 | yes | 6.74 | 0.030 | 0 | 363 | heavy.mp4 |
| slippery | friction_coefficient 0.2 | yes | 6.68 | 0.007 | 0 | 360 | slippery.mp4 |
| sticky | friction_coefficient 1.0 | yes | 6.80 | 0.007 | 0 | 366 | sticky.mp4 |
| offset_pos | object_offset_m +0.10 | yes | 9.20 | 0.006 | 0 | 485 | offset_pos.mp4 |
| offset_neg | object_offset_m -0.10 | yes | 9.36 | 0.007 | 0 | 493 | offset_neg.mp4 |
| delay_100 | observation_delay_ms 100 | yes | 6.56 | 0.006 | 0 | 354 | delay_100.mp4 |
| **delay_200** | observation_delay_ms 200 | yes | 10.06 | 0.016 | **46** | 528 | delay_200.mp4 |
| **combo** | friction 0.2 + delay 200 ms + offset +0.10 | yes | 9.64 | 0.017 | **44** | 507 | combo.mp4 |

Numbers are copied from `evidence/G05/g05_run_report.json`. "Goal reached
(provisional)" is the episode runner's convenience check (block centre within
the 0.04 m target radius for 25 consecutive control steps); it is **not** the
oracle verdict. The oracle arrives in G06.

**Forbidden contacts.** In `delay_200` and `combo` the closed fingers scrape the
floor during the descent and the push (contact pairs `world/floor` vs
`left_finger/*` and `right_finger/*`; first at t = 3.62 s and 2.90 s; peak
normal force 28.7 N and 21.1 N; from the saved contact telemetry). Under the
collision rule the adapter encodes (`robot_collision_pairs`: any arm link or
hand against anything, fingers against the floor; PROPOSED, to be frozen in
the G06 TestSpec) these two episodes are real failures of the policy even
though the block ends in the target. The 200 ms observation delay makes the
controller overshoot its descent height. This is exactly the kind of failure
the project exists to find; it was not planted.

**Replay.** Running the nominal scenario twice in the same process gave
byte-identical trajectories: 360 steps compared, max |delta qpos| = 0.0, max
|delta object position| = 0.0 (`replay.bit_identical: true`). Tolerance for
replay across processes or machines will be set in G06 from measured drift,
not assumed.

**Throughput.** Rendered episodes run at about 0.15x real time on this
laptop (48 to 74 s wall per episode, dominated by rendering and MP4 encoding
on the `/mnt/c` filesystem). The unrendered replay ran at 10.9x real time
(0.7 s wall for a 7.2 s episode). Sweeps in G07+ run unrendered.

## Acceptance check (runbook G05 and spec 13.1)

| Requirement | Result |
|---|---|
| Nominal episode succeeds | `nominal`: block pushed 0.30 m into the target, held, no forbidden contacts |
| A real failed episode | `delay_200`, `combo`: 46 / 44 control steps of fingers-on-floor contact, recorded in telemetry. Final label is the oracle's (G06), but the contact is real and was not scripted |
| Per-step trajectory | every episode saves `Trajectory` (qpos, qvel, block and end-effector position, applied control, all contacts with normal force, applied delay) validated by the G02 schemas |
| Truthful video | 9 MP4s rendered from the simulator's `demo` camera during the same closed-loop run that produced the trajectory; frames were checked by eye (nominal at t = 5 s shows the fingers pushing the block toward the target disk) |
| Two effective perturbations, with tests proving effect | four implemented: mass (body mass and inertia scaled, `mj_setConst`), friction (block and floor geom sliding friction), start offset (free-joint qpos), observation delay (time-indexed history buffer). `tests/test_mujoco_adapter.py` asserts each one changes the compiled model or the returned observation. Mass and friction changed outcomes only slightly in this handful of runs; offset and delay changed them a lot. Whether mass/friction matter inside the domain is a G07 question, not assumed either way |
| Toleranced replay | bit-identical in-process; see above |
| Latency semantics documented | below |
| Policy labelled honestly | `PolicyManifest.kind = classical`, id `push-dls-ik-v1`, source hash recorded. It is damped-least-squares differential inverse kinematics with a four-phase state machine. Not learned, not GR00T |
| Model licence recorded | Menagerie Panda `LICENSE` is Apache-2.0 (copy in evidence; `docs/sources.md` S08 updated) |

## Observation delay semantics (DECIDED for the MVP)

- The adapter keeps a history buffer of `(sim_time, raw_observation)` pushed
  once per control step (every 20 ms) plus the reset state at t = 0.
- `observe()` returns the newest buffered state captured at or before
  `now - delay`. The returned `Observation` records `sim_time_s` (now),
  `source_sim_time_s` (capture time) and `delay_applied_ms`. The schema refuses
  observations from the future.
- Because the buffer is sampled at the control period, the delay actually
  applied is rounded **up** to a multiple of 20 ms; a 100 ms setting is exactly
  5 control steps. During the first `delay` seconds after reset the oldest
  available state (t = 0) is returned, so the applied delay ramps from 0 to the
  setting; this is recorded per observation.
- The whole observation vector is delayed together (end-effector, block,
  target, joint angles, joint velocities). The controller closes its loop on
  the delayed end-effector and block positions and uses the delayed joint
  angles for its Jacobian, so delay affects both what it sees and how it moves.

## Design notes

- **Scene staging.** The Menagerie `panda.xml` is never edited in place. A
  derived copy drops the 9-DoF `home` keyframe (our scene has a free block, so
  nq = 16) and adds an `ee_site` at the fingertip pinch point; a generated
  `push_scene.xml` adds floor, block, target disk, camera and a full keyframe.
  Both staged files are hashed into `scene_sha256`
  (`66b5b39e65dbe6366486019e744c4c45c12b296de92eff40e495f9b7fb463f35`).
- **Observation vector** is fixed in `skuld/core/observation_layout.py`
  (23 values). The domain only contains variables that change these values or
  the dynamics producing them; camera and lighting are deliberately absent
  because the policy does not see pixels.
- **Two controller bugs found by running, not by reading.** (1) Integrating
  the IK velocity from the measured joint angles let the position actuators'
  gravity sag swallow each increment, so the arm crept and stalled; the command
  is now integrated as controller state and the loop closes on the observed
  end-effector error. (2) Position-only IK let the hand tilt until its side hit
  the floor; the IK is now 6-DoF and holds the home hand orientation. Both are
  evidence for rule 3: nothing passes because code exists.
- **Fingers are closed** (gripper control 0) so the policy pushes with the
  fingertips; grasping is out of scope.
- The MuJoCo tests skip cleanly when `SKULD_MENAGERIE_DIR` is unset or
  `mujoco` is not importable, so CI (ubuntu, app deps only) still runs the 35
  contract tests and reports the 9 simulator tests as skipped, never as passed.

## Cost and approval

No spend. No provisioning. Network: PyPI and one sparse `git clone` of the
Menagerie repository.
