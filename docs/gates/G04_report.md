# G04 | Install NPA + genuine Nemotron call

```yaml
schema_version: skuld.gate-report.v1
gate: G04
status: PASS           # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<commit that carries this report; see git log>'
environment: 'WSL2 Ubuntu 24.04.5. npa venv ~/.venvs/npa: npa 0.1.0 from the pinned nebius-physical-ai checkout (commit 10102f5102bd3a7bbefc62d195f1b1f3646f5816, cloned 2026-10-29T02:24:18Z, evidence/G04/npa-pin.txt). App venv ~/.venvs/skuld for the direct catalog GET. Sim venv ~/.venvs/skuld-mujoco (mujoco 3.17.0) for the executed scenario. Key: NEBIUS_TOKEN_FACTORY_API_KEY in the git-ignored .env, exported for the CLI as NEBIUS_TOKEN_FACTORY_KEY (the variable named in the pinned docs/workbench/token-factory-key.md, DOC-VERIFIED); never written to evidence (scrub + prefix scan in scripts/g04_run.sh).'
commands:
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_setup.sh'                                        # step 1: pinned clone, npa venv, --help capture (no Token Factory call)
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_run.sh catalog'                                  # step A: status, verify, models (read-only, not inference)
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_run.sh propose nvidia/Nemotron-3_5-Lightning'  # step B: the inference call (run twice, see below)
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/g04_run.sh execute "Adam Crozier"'                  # step C: approval, domain check, scenario, oracle (local sim, no spend)
  - 'wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Skuld/scripts/quick_check.sh <g04 files>'                         # ruff format/check + pytest, app venv
evidence_paths:
  - evidence/G04/npa-pin.txt                      # repo, commit, clone time, path
  - evidence/G04/npa-version.txt                  # npa 0.1.0
  - evidence/G04/npa-token-factory-help.txt       # installed --help for token-factory, status, verify, models, generate (flags used below come from here)
  - evidence/G04/token-factory-doc-head.txt       # head of the pinned docs/workbench/token-factory.md
  - evidence/G04/npa-status.json                  # api_key_configured true, base_url, npa defaults
  - evidence/G04/npa-verify.json                  # authenticated true, model_count 30 (model-list call, "does not test inference or billing access")
  - evidence/G04/npa-models.json                  # CLI catalog listing
  - evidence/G04/models_list.json                 # direct GET /v1/models?verbose=true: request_id, 30 ids, 5 nvidia/* with pricing and context length
  - evidence/G04/prompts.jsonl                    # the two prompts sent (constraint extraction over the G08 Tavily snippets; hypothesis over the locked domain)
  - evidence/G04/generations.jsonl                # THE RUNTIME ARTIFACT: raw npa generate output, two rows {id, prompt, completion}, redacted
  - evidence/G04/generate_call.json               # model id, flags, timestamps, exit code, sha256 of generations.jsonl, validation outcome per completion
  - evidence/G04/attempt1_rejected/               # first call: same artifacts; constraint completion rejected by the verbatim-quote check, kept unpatched
  - evidence/G04/constraints/proposed/panda-payload-kg-nemotron.json
  - evidence/G04/constraints/approved/panda-payload-kg-nemotron.json
  - evidence/G04/domain_check.json
  - evidence/G04/hypothesis_nemotron.json         # model_id nvidia/Nemotron-3_5-Lightning, box inside the locked domain
  - evidence/G04/scenario.json
  - evidence/G04/scenario.trajectory.json
  - evidence/G04/scenario.result.json             # oracle EpisodeResult: SAFETY_FAIL, NEVER collision
  - evidence/G04/g04_report.json
  - evidence/G04/g04_run.log
provider_run_ids:
  - 'GET https://api.tokenfactory.nebius.com/v1/models?verbose=true: HTTP 200, request_id cb3fdabd0c824c5528392c281e30e380, 2026-10-29T02:36:21Z, 0.463 s, 30 models'
  - 'npa workbench token-factory generate, attempt 1: started 2026-10-29T02:37:50Z, 4.52 s, exit 0, generations sha256 6ea23ac47bba1bd6f58458ab3d670e7f8723ed86fdf5e82b9b192f1b7e8c07fd (npa exposes no provider request id or token usage for generate)'
  - 'npa workbench token-factory generate, attempt 2: started 2026-10-29T02:41:51Z, 4.07 s, exit 0, generations sha256 5072ab1674f515876215b9c008527ff2b59534cefa959c2514aceb923d514713'
actual_test_results:
  - 'ruff check .: All checks passed (exit 0), after ruff format of the five G04 files'
  - 'python -m pytest -q -ra (app venv): 73 passed, 1 skipped (MuJoCo adapter module, no Menagerie path in that venv), exit 0; two of the 73 are the new tests/test_token_factory.py'
  - 'scripts/g10_check.sh (sim venv, Menagerie path set): ruff clean, 82 passed in 3.22s, exit 0'
  - 'catalog: status api_key_configured true; verify authenticated true, 30 models; direct GET 200 with 5 nvidia/* ids'
  - 'propose attempt 1: both completions nonempty; constraint REJECTED ("quote does not occur verbatim in the cited snippet"); hypothesis accepted'
  - 'propose attempt 2: both completions nonempty; constraint accepted (3.0 kg, datasheet PDF, quote verbatim); hypothesis accepted (observation_delay_ms [100, 200])'
  - 'execute: domain consistent; scenario delay 200 ms, others nominal; oracle SAFETY_FAIL, NEVER collision, 0.73 s wallclock'
spend_approved: true
approved_by: 'Adam Crozier (in chat, 2026-10-28 evening local): proceed with the cheapest NVIDIA model and keep spend minimal. Two generate calls at the listed Nemotron-3_5-Lightning prices (USD 0.06 per M prompt tokens, 0.24 per M completion tokens) with about 9 k prompt characters and under 1 k completion characters per call: well under one US cent in total (estimate from character counts; npa reports no usage). Adam Crozier approved the Nemotron-proposed constraint panda-payload-kg-nemotron at 2026-10-29T02:43:22Z (recorded in the approved file).'
blockers: []
next_action: 'Human items only: confirm R3/R4 on the Devpost rules page with this evidence in hand (docs/rules.md), G03 credit balance check, record the video with the Nemotron step included, secret scan, flip the repo public, submit.'
```

## What was proven, in CLAUDE.md terms

| Claim | Status | Where |
|---|---|---|
| The pinned npa CLI is installed and its flags were read before use | EXECUTED | `npa-pin.txt`, `npa-version.txt`, `npa-token-factory-help.txt` |
| The key authenticates against Token Factory | EXECUTED (model-list call, not inference) | `npa-verify.json`, `models_list.json` |
| `nvidia/Nemotron-3_5-Lightning` is in the catalog visible to our key | EXECUTED | `models_list.json` (five `nvidia/*` ids; this one has 1,048,576 context, text->text) |
| A real `generate` call returned nonempty completions from that model id | EXECUTED | `generations.jsonl`, `generate_call.json` (and `attempt1_rejected/` for the first call) |
| The completions were validated, not trusted | EXECUTED | `generate_call.json` validation block; `tests/test_token_factory.py` |
| A Nemotron-authored hypothesis was executed in the simulator and judged by the oracle | EXECUTED | `hypothesis_nemotron.json`, `scenario.json`, `scenario.result.json` |
| Nemotron controlled the robot, set a threshold, or decided pass/fail | never; not claimed | the oracle reads the trajectory only; `check_against(domain)` refuses out-of-bounds boxes |

Rules R3 (NVIDIA open model) and R4 (Token Factory runtime call) are now backed
by a runtime artifact in this repository. Whether the artifact satisfies the
judges is still the human's confirmation on the Devpost rules page.

## The chain, as executed (EXECUTED 2026-10-28 evening local / 2026-10-29 UTC)

| Step | What happened | Who decided |
|---|---|---|
| 1. Pin + install | `git clone nebius/nebius-physical-ai` at commit `10102f51`, `pip install -e npa` into `~/.venvs/npa`, `--help` of every subcommand captured before any call | code |
| 2. Catalog | `status` (key configured), `verify` (authenticated, 30 models), `models`, plus a direct `GET /v1/models?verbose=true` for pricing and context length. Five `nvidia/*` models visible. Not inference, not claimed as such | runtime calls, recorded |
| 3. Model choice | `nvidia/Nemotron-3_5-Lightning`: the npa default text model, the cheapest `nvidia/*` text model in the listing. The runner refuses to run without an explicit `--model` and refuses any id outside `nvidia/` | **human** (cost constraint stated in chat) |
| 4. Prompts | two rows in the documented `{"id","prompt"}` JSONL format: (a) extract the rated payload from the five G08 Tavily snippets, which are labelled DATA; (b) propose one falsification box over at most two variables inside the locked `push-v1` bounds, given the G07/G10 observed facts and the human-approved G08 constraint | code |
| 5. Call, attempt 1 | `generate --model nvidia/Nemotron-3_5-Lightning --temperature 0 --max-tokens 600 --output json`; 4.52 s; both completions nonempty. Constraint completion: value 3, correct unit, a URL from the results, but quote `"Payload 3.0 kg"` where the RoboDK snippet says `"payload of 3 kg"`: **rejected** by the verbatim-substring check and recorded unpatched. Hypothesis: delay [140, 200], accepted | model proposes; validator refuses |
| 6. Prompt fix | the extraction prompt now says the quote is matched as an exact substring and must not reformat numbers (neutral example, no answer leaked). Attempt 1 artifacts moved to `attempt1_rejected/` | code change, tests still pass |
| 7. Call, attempt 2 | same flags; 4.07 s; constraint `object_mass_kg <= 3.0 kg`, source the Franka Emika Panda datasheet PDF (wiredworkers.io mirror from the G08 results), quote `"Payload 3 kg"` verbatim, confidence 1.0: **accepted** as PROPOSED. Hypothesis: "Increasing observation_delay_ms beyond 100 ms while keeping other variables nominal will cause the finger to touch the floor before the push completes", box delay [100, 200], citing the random-baseline and minimization facts it was given: **accepted**, inside the domain | model proposes; validator checks |
| 8. Human review | the proposed constraint (value, source, quote) and the hypothesis were shown in chat; Adam approved the constraint under his name | **human** |
| 9. Domain check | documented 3.0 kg vs locked [0.05, 0.5] kg: consistent, no bound change | code reports |
| 10. Executed scenario | corner of the box: delay 200 ms, mass 0.1 kg, friction 0.6, offset 0 (distance from nominal 1.0), 15 s in MuJoCo | simulator |
| 11. Verdict | **SAFETY_FAIL**, `NEVER collision`: left finger on the floor from t = 3.62 s, 46 control steps, peak normal 28.7 N (reported, no limit claimed); block reached the target at 10.06 s | deterministic oracle |

The hypothesis was confirmed on this one scenario. It is the same failure
mechanism already seen in G05, G07 and G10 (the model was told about those
results), so this is a check that the chain works end to end with a model in
the author's seat, not a new discovery.

## Acceptance check (spec 13.1 row G04)

| Requirement | Result |
|---|---|
| Pinned checkout, `npa --version` | commit `10102f5102bd3a7bbefc62d195f1b1f3646f5816`, npa 0.1.0 |
| `npa configure --no-provision` | **not run.** The key was supplied through `NEBIUS_TOKEN_FACTORY_KEY`, the environment option the pinned `token-factory-key.md` documents; `status` reports `api_key_configured: true`. Nothing was provisioned |
| `token-factory status / verify / models` | all three executed, JSON saved |
| Real `generate` with nonempty completion from a listed NVIDIA model | yes, twice; model id recorded in every artifact |
| Hypothesis JSON validated against the allowlist | `HypothesisProposal` and `ConstraintProposal` are `extra='forbid'`; `Hypothesis.check_against(PUSH_V1)` refuses unknown variables and out-of-bounds boxes; a completion with no JSON object, a foreign URL, a non-verbatim quote, a wrong unit or a non-positive value is refused (`tests/test_token_factory.py`) |
| Redacted JSONL, model id, CLI logs, commit hash | `generations.jsonl` (key scrubbed, bearer pattern scrubbed, prefix scan clean), `generate_call.json`, `g04_run.log`, `npa-pin.txt` |

## Honest notes

- **Temperature 0 did not reproduce.** The same hypothesis prompt returned
  delay [140, 200] on attempt 1 and [100, 200] on attempt 2. Reproducibility of
  the model step lives in the archived JSONL and its sha256, not in the sampler.
- **No provider request id or token usage for `generate`.** The npa CLI does
  not surface them; the call is identified by its timestamps, exit code and the
  sha256 of its output. The direct catalog GET does carry a request id.
- **The validator caught a real error.** Attempt 1 paraphrased the quote. The
  fix was to the prompt, not to the output; the rejected artifact is kept.
- **Cost is an estimate.** Under one cent by character count at the listed
  prices; no billing figure was observed. G03 credit confirmation remains a
  human item.
- **What the model did not do.** It did not touch the simulator, the oracle,
  the protocol, the domain bounds, or the release gate. The pass/fail path is
  unchanged from G06.

## Cost and approval

Two Token Factory inference calls, estimated under USD 0.01 total, approved by
Adam Crozier in chat with the instruction to keep spend minimal. No cloud
compute, no provisioning, no account changes. About one minute of laptop time
for the executed scenario.
