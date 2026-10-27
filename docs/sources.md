# Source register

Epistemic labels: **DOC-VERIFIED** = page seen in official docs on the date given. **EXECUTED** = run in our environment with evidence saved. **PINNED** = we have recorded the exact commit or version we depend on. Repository `main` branches move; clone and pin before relying on a command.

## Project documents

| Ref | Document | Location |
|---|---|---|
| D1 | BoundaryLab concept and deep-research pitch, 2026-10-24 | `docs/source-pdfs/BoundaryLab_ The Physical AI Project I Would Bet the Hackathon On.pdf` |
| D2 | BoundaryLab Verified Engineering Runbook, Team ODIN, 2026-10-25 | `docs/source-pdfs/BoundaryLab_Verified_Engineering_Runbook_Team_ODIN.pdf` |
| D3 | Skuld specification | `spec.md` |
| D4 | Claude Code operating rules | `CLAUDE.md` |

## Vendor and platform sources

| Ref | Resource | URL | Status | Pinned version / commit |
|---|---|---|---|---|
| S01 | Devpost hackathon rules | https://nebiusglobalaihackathon.devpost.com/rules | DOC-VERIFIED by D2 author 2026-10-25; Claude gets HTTP 403 | n/a |
| S01b | Devpost resources (credits) | https://nebiusglobalaihackathon.devpost.com/resources | UNVERIFIED by Claude (403) | n/a |
| S02 | Nebius Physical AI Workbench README + quickstart | https://github.com/nebius/nebius-physical-ai ; `docs/quickstart.md` | DOC-VERIFIED 2026-10-25 (platforms: macOS, Linux, WSL2 Ubuntu; Python 3.11+; `pip install -e npa` from checkout) | commit: _pin in G04_ |
| S03 | Token Factory CLI docs | https://github.com/nebius/nebius-physical-ai/blob/main/docs/workbench/token-factory.md | DOC-VERIFIED by D2 author 2026-10-25 | commit: _pin in G04_ |
| S04 | NPA workflow guide + CLI reference | `docs/workbench/npa-workflow-guide.md` ; `docs/cli/workflow.md` in S02 repo | DOC-VERIFIED by D2 author 2026-10-25 | not needed while G09 is OFF |
| S05 | MuJoCo Python bindings | https://mujoco.readthedocs.io/en/stable/python.html | DOC-VERIFIED by D2 author; EXECUTED 2026-10-25: `mujoco-3.17.0-cp312-cp312-win_amd64.whl` downloads | mujoco 3.17.0 (latest on PyPI 2026-10-25) |
| S06 | Isaac Lab | https://github.com/isaac-sim/IsaacLab | DOC-VERIFIED by D2 author | stretch only |
| S07 | Isaac GR00T N1.7 | https://github.com/NVIDIA/Isaac-GR00T | DOC-VERIFIED by D2 author | stretch only |
| S08 | MuJoCo Menagerie (Franka Panda model) | https://github.com/google-deepmind/mujoco_menagerie | DOC-VERIFIED by D2 author; EXECUTED 2026-10-26: sparse clone of `franka_emika_panda/` | commit `f3b6013629c7b94f8ee93fd977b161fa8350f9bc`; `franka_emika_panda/LICENSE` is Apache-2.0 (copy in `evidence/G05/panda-model-LICENSE.txt`), compatible with our Apache-2.0 |
| S09 | Tavily Search API and Python SDK | https://docs.tavily.com/documentation/api-reference/endpoint/search ; https://github.com/tavily-ai/tavily-python | DOC-VERIFIED by D2 author; EXECUTED 2026-10-25: `tavily_python-0.8.5` wheel downloads | tavily-python 0.8.5 |
| S10 | Nebius CLI install | https://docs.nebius.com/cli/install | DOC-VERIFIED 2026-10-25: Ubuntu and macOS only; `curl -sSL https://artifacts.nebius.cloud/cli/install.sh \| bash` | version: _pin to the one S02 quickstart names, in G04_ |
| S11 | Claude Code quickstart | https://code.claude.com/docs/en/quickstart | DOC-VERIFIED by D2 author | Claude Code 2.1.310 installed on host |
| S12 | Claude Code permissions | https://code.claude.com/docs/en/permissions | DOC-VERIFIED by D2 author | n/a |
| S13 | NVIDIA Cosmos | https://github.com/NVIDIA/cosmos | DOC-VERIFIED by D2 author | stretch only |
| S14 | Nebius Builder Program | https://dev.nebius.com/builders ; https://nebius.com/builders-terms-and-conditions | DOC-VERIFIED 2026-10-25: USD 25 Token Factory + USD 25 Tavily, 90-day expiry | n/a |
| S15 | Nebius promo code redemption | https://docs.nebius.com/signup-billing/payments/promo-codes | DOC-VERIFIED 2026-10-25: requires payment details; card adds a USD 25 charge credited to balance | n/a |
| S16 | Docker Engine install (Ubuntu) | https://docs.docker.com/engine/install/ubuntu/ | DOC-VERIFIED by D2 author | not needed for MVP |

## Research references

| Ref | Paper | URL |
|---|---|---|
| R1 | Causal Falsification of Digital Twins, JMLR 2026 | https://www.jmlr.org/beta/papers/v27/24-1752.html |
| R2 | Learning of Robot Safety Policies via Adversarial Synthetic Scenarios, 2026 | https://arxiv.org/abs/2606.05952 |
| R3 | RoboTTT: Context Scaling for Robot Policies, 2026 | https://arxiv.org/abs/2607.15275 |
| R4 | Learning Robot Policies from Sparse Success Signals via STL-Guided Stein Variational Policy Gradient, 2026 | https://arxiv.org/abs/2609.31606 |

## Context sources cited in the pitch (not load-bearing for the build)

| Ref | Resource | URL |
|---|---|---|
| C1 | Nebius Physical AI Living Lab announcement | https://nebius.com/newsroom/nebius-launches-physical-ai-living-lab-for-uk-and-european-robotics-startups-built-with-nvidia-technologies |
| C2 | NVIDIA role postings (Principal Engineer AV and Physical AI; Director Engineering AV; Sr SWE Low Latency Physical AI Sensor Systems; Director PM Agent Tooling) | nvidia.wd5.myworkdayjobs.com |

## Naming check (EXECUTED 2026-10-25, see `evidence/G00/name-availability.txt`)

| Handle / domain | Result |
|---|---|
| github.com/skuld | taken (HTTP 200) |
| github.com/skuld-ai | taken (HTTP 200) |
| github.com/skuld-odin | available (HTTP 404) |
| github.com/skuldai | available (HTTP 404) |
| skuld.ai | has DNS records (registered) |
| skuld.dev | has DNS records (registered) |
| skuldai.com | no DNS records (likely available; confirm with a registrar) |
| skuld-ai.com | no DNS records (likely available; confirm with a registrar) |
