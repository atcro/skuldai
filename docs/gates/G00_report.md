# G00 | Freeze rules, scope and owners

```yaml
schema_version: skuld.gate-report.v1
gate: G00
status: BLOCKED        # PASS | FAIL | BLOCKED | NOT_STARTED
source_revision: '<first commit hash, pending>'
environment: 'Windows 11 Pro host, Git Bash; no WSL2 Ubuntu yet'
commands:
  - 'curl -s -o /dev/null -w "%{http_code}" https://github.com/{skuld,skuld-ai,skuld-odin,skuldai}'
  - 'nslookup {skuld.ai,skuld.dev,skuldai.com,skuld-ai.com}'
  - 'git init -b main'
evidence_paths:
  - evidence/G00/name-availability.txt
  - docs/rules.md
  - docs/scope.md
  - docs/sources.md
  - spec.md#17
provider_run_ids: []
actual_test_results: []
spend_approved: false
approved_by: null
blockers:
  - 'Human must re-confirm every row of docs/rules.md on Devpost while logged in (Claude gets HTTP 403).'
  - 'Human must confirm Devpost registration, team membership and submission owner.'
  - 'Human must confirm the Devpost activation code NEBIUS-DEVPOST-GLOBAL26 exists on the resources page.'
next_action: 'Laptop owner confirms rules + registration, ticks boxes in docs/rules.md, then flip status to PASS and record the commit hash.'
```

## Prerequisites

- Source documents D1 and D2 read in full (2026-10-25).
- Twelve open questions reviewed with the team and decided (spec.md section 17).

## What was done

| Runbook step | Result |
|---|---|
| 01 Read official rules, write `docs/rules.md` | Written from D2's live check of 2026-10-25. Human confirmation column is empty. |
| 02 Confirm eligibility, team, originality | Pending human. No prior code exists; everything is new work. |
| 03 Register / confirm Devpost and submission owner | Submission owner decided: laptop owner. Registration confirmation pending human. |
| 04 Project identifier, track, license | Name **Skuld**; track **Physical AI**; license **Apache-2.0**. GitHub handles `skuld` and `skuld-ai` are taken; `skuld-odin` and `skuldai` are free. |
| 05 Ownership lanes | Two humans, one laptop, one development window. Serial keyboard lane plus off-keyboard review lane. See spec.md section 14.1. |
| 06 Define MVP | `docs/scope.md`: Panda, push task, one scene, 2 to 4 perturbations, deterministic oracle. |
| 07 Budget | Zero paid spend. Budget owner: laptop owner. Token Factory only if covered by credits. |
| 08 `docs/sources.md` and `docs/gates/` | Created. |

## Cost and approval

No spend. No provisioning.

## Next gate

G01: install WSL2 Ubuntu 24.04 (human, elevated PowerShell), then toolchain inside it.
