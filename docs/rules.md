# Hackathon rules as they bind Skuld

**Event:** Nebius x NVIDIA Global AI Hackathon, Physical AI track
**Rules page:** https://nebiusglobalaihackathon.devpost.com/rules
**Status of this file:** facts below were live-checked on 2026-10-25 by the author of the engineering runbook (see `docs/sources.md`, S01). Claude could not re-fetch Devpost (HTTP 403 to automated fetchers). **A human must re-confirm every row while logged in to Devpost and tick the box.** Until then G00 stays BLOCKED.

## Binding constraints

| # | Rule | Value we are working to | Confirmed by human |
|---|---|---|---|
| R1 | Submission deadline | **Fri 2026-10-30, 10:00 AM PDT / 1:00 PM EDT / 17:00 UTC** | [ ] |
| R2 | Internal target | Submit **Thu 2026-10-29**. Oct 30 morning is emergency buffer only. | n/a |
| R3 | NVIDIA model requirement | At least one NVIDIA open model must be used. We satisfy it with a Nemotron model via Nebius Token Factory. | [ ] |
| R4 | Nebius runtime requirement | The application must make a runtime call to Nebius Token Factory **or** run on Nebius AI Cloud compute. Either is sufficient. We use Token Factory. | [ ] |
| R5 | Physical AI track, simulation | Simulation-only projects are permitted. | [ ] |
| R6 | Video | Public YouTube video, **under** 3:00. At least one minute must visibly show the key application modules operating. No fabricated speed-ups or results. | [ ] |
| R7 | Repository | Public repository with a visible open-source LICENSE and reproducible instructions. | [ ] |
| R8 | Judging | Viability/fit gate, then four equally weighted dimensions: Technological Implementation, Design, Potential Impact, Quality of the Idea. Organizers state a scripted Physical AI demo is table stakes. | [ ] |
| R9 | Tavily bonus | USD 3,000 bonus requires a functional **runtime** Tavily API call. | [ ] |
| R10 | Prize stacking | A project may receive an overall award, or a track award plus one bonus award. Overall prizes do not stack. | [ ] |
| R11 | Eligibility and originality | Team members must be eligible entrants. Work must be original; if any prior code predates the contest, document the significant new work. | [ ] |
| R12 | Submission form | Devpost project page, selected track Physical AI, YouTube URL, repo URL. Submitted by the submission owner. | [ ] |

## Credits (fact-finding, not rules)

| Route | Reported benefit | Epistemic status | Action |
|---|---|---|---|
| Devpost activation code `NEBIUS-DEVPOST-GLOBAL26` | USD 25 Token Factory credit via a form on the Devpost resources page | UNVERIFIED by Claude (403). Reported by web search summaries of the resources page. | Human confirms on https://nebiusglobalaihackathon.devpost.com/resources while logged in |
| Nebius Builder Program | USD 25 Token Factory + USD 25 Tavily per verified email; expire 90 days after issuance; educational or corporate email preferred | DOC-VERIFIED 2026-10-25 at https://nebius.com/builders-terms-and-conditions and https://dev.nebius.com/builders | Apply with the .edu address; verify email |
| AI Cloud promo codes | Require payment details; adding a card triggers a USD 25 charge credited to balance | DOC-VERIFIED at https://docs.nebius.com/signup-billing/payments/promo-codes | **Do not add a card** under the zero-spend decision |

## Our additional self-imposed rules

- No metric in the README or video that does not come from an archived run artifact.
- "Eligible" means "passed the named simulation suite", never "safe".
- Every claimed integration (Nemotron, Tavily, Nebius) must have a runtime artifact in `evidence/`.
- Mock or demo-only screens are labelled on screen.

## Human confirmation record

- Confirmed by: _pending_
- Date: _pending_
- Devpost registration and team membership confirmed: _pending_
- Submission owner: laptop owner (decided 2026-10-25)
