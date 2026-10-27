"""Evidence -> DocumentedConstraint -> human approval -> Hypothesis chain (spec 10).

Rules enforced here, not by convention:

- A constraint extracted from fetched text is PROPOSED. It changes nothing.
- Only a human can approve (`approve_constraint` takes an authorizer name;
  Claude never calls it on its own, CLAUDE.md rule 7).
- `check_domain` never mutates the domain. If a documented limit is tighter
  than the locked domain it *reports* the tightened bounds; adopting them is a
  new protocol version, done by a human.
- A Hypothesis must pass `check_against(domain)`; anything outside the
  allowlist or bounds is rejected before any scenario is built.
- Fetched text is data. The extractor is a regex over a snippet; the snippet
  is stored verbatim as `quote_or_paraphrase` and has no other effect.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from skuld.core.schemas import (
    ApprovalState,
    DocumentedConstraint,
    Hypothesis,
    HypothesisVariable,
    PerturbationDomain,
    Scenario,
)
from skuld.integrations.tavily.search import TavilyHit, TavilySearchRecord

# "payload 3 kg", "payload: 3kg", "3 kg payload", "payload of up to 3 kg"
_PAYLOAD_RE = re.compile(
    r"(?:payload\D{0,40}?(\d+(?:[.,]\d+)?)\s*kg)|(?:(\d+(?:[.,]\d+)?)\s*kg\s+payload)",
    re.IGNORECASE,
)


class UnapprovedConstraintError(RuntimeError):
    pass


def extract_payload_kg(text: str) -> float | None:
    """Deterministic extraction of a payload figure in kg from untrusted text, else None."""
    m = _PAYLOAD_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def propose_payload_constraint(
    record: TavilySearchRecord,
    *,
    constraint_id: str,
    property_name: str = "object_mass_kg",
    prefer_domains: tuple[str, ...] = (),
) -> tuple[DocumentedConstraint, TavilyHit] | None:
    """First hit (preferring given domains) whose snippet yields a payload figure."""
    ordered = sorted(
        record.results,
        key=lambda h: (not any(d in str(h.url) for d in prefer_domains), -(h.score or 0.0)),
    )
    for hit in ordered:
        value = extract_payload_kg(hit.content)
        if value is None:
            continue
        c = DocumentedConstraint(
            constraint_id=constraint_id,
            property=property_name,
            value=value,
            unit="kg",
            source_url=hit.url,
            quote_or_paraphrase=hit.content[:2000],
            extraction_confidence=0.6,  # regex over a search snippet; not a model, not a human
            retrieved_at=record.finished_utc,
        )
        return c, hit
    return None


def approve_constraint(c: DocumentedConstraint, authorizer: str) -> DocumentedConstraint:
    """Human-only. Returns an approved copy; the proposed object is unchanged."""
    return c.model_copy(
        update={
            "approval_state": ApprovalState.APPROVED,
            "authorizer": authorizer,
            "approved_at": datetime.now(UTC),
        }
    )


def check_domain(domain: PerturbationDomain, c: DocumentedConstraint) -> dict:
    """Compare the locked domain with an *approved* constraint. Never mutates anything.

    For a payload-type limit the admissible object mass is [min, documented value].
    """
    if c.approval_state is not ApprovalState.APPROVED:
        raise UnapprovedConstraintError(
            f"constraint {c.constraint_id} is {c.approval_state}; a human must approve it "
            "before it may be compared with, let alone change, any bound"
        )
    if c.property not in domain.names:
        return {
            "property": c.property,
            "in_domain": False,
            "consistent": None,
            "note": "not a domain variable",
        }
    spec = domain.spec(c.property)
    consistent = spec.max <= c.value
    out = {
        "property": c.property,
        "in_domain": True,
        "domain_min": spec.min,
        "domain_max": spec.max,
        "documented_limit": c.value,
        "unit": c.unit,
        "consistent": consistent,
    }
    if not consistent:
        out["proposed_tightened_max"] = c.value
        out["note"] = (
            "domain exceeds the documented limit; adopting the tightened bound requires a new "
            "protocol version approved by a human. Not applied here."
        )
    return out


def hypothesis_from_constraint(
    domain: PerturbationDomain,
    c: DocumentedConstraint,
    record: TavilySearchRecord,
    *,
    author: str,
    delay_window_ms: tuple[float, float] = (150.0, 200.0),
) -> Hypothesis:
    """A human/placeholder-authored hypothesis tied to the evidence. Nemotron takes this
    role in G04+; until then `model_id` says exactly who authored it (rule 8)."""
    if c.approval_state is not ApprovalState.APPROVED:
        raise UnapprovedConstraintError("hypotheses are only built from approved constraints")
    mass = domain.spec("object_mass_kg")
    delay = domain.spec("observation_delay_ms")
    h = Hypothesis(
        hypothesis=(
            f"At the heaviest admissible object ({mass.max} kg, within the documented payload "
            f"limit of {c.value} {c.unit}) combined with observation delay in "
            f"[{delay_window_ms[0]}, {delay_window_ms[1]}] ms, the push controller overshoots "
            "its descent and the fingers touch the floor."
        ),
        variables=[
            HypothesisVariable(
                name="object_mass_kg", min=max(mass.min, mass.max * 0.8), max=mass.max
            ),
            HypothesisVariable(
                name="observation_delay_ms",
                min=max(delay.min, delay_window_ms[0]),
                max=min(delay.max, delay_window_ms[1]),
            ),
        ],
        reason_to_test=(
            "G07 random baseline: all 3 of 3 valid failures had delay >= 152 ms; mass effect "
            "unknown. The documented payload bounds how heavy an object is worth testing."
        ),
        expected_failure_signature="SAFETY_FAIL: NEVER collision (finger vs floor) during descent",
        model_id=author,
        request_id=record.request_id or f"local-{record.started_utc.strftime('%Y%m%dT%H%M%SZ')}",
        evidence_refs=[c.constraint_id, str(c.source_url)],
    )
    h.check_against(domain)
    return h


def scenario_from_hypothesis(
    h: Hypothesis, domain: PerturbationDomain, *, scenario_id: str, seed: int
) -> Scenario:
    """Deterministic corner of the hypothesis box: every named variable at its max,
    everything else nominal. Checked against the domain before it is returned."""
    h.check_against(domain)
    values = domain.nominal_values()
    for hv in h.variables:
        values[hv.name] = hv.max
    sc = Scenario(scenario_id=scenario_id, domain_ref=domain.domain_id, values=values, seed=seed)
    sc.check_against(domain)
    return sc
