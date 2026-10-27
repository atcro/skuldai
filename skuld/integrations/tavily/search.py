"""One live Tavily search with full provenance (spec 10, runbook G08).

DOC-VERIFIED 2026-10-26 against https://docs.tavily.com/documentation/api-reference/endpoint/search
and the installed tavily-python 0.8.5 signature: `TavilyClient.search(query, search_depth=
'basic'|'advanced'|'fast'|'ultra-fast', max_results=0..20, include_domains=[...],
include_domains_mode='restrict'|'prefer', ...)`; the response carries `results[]`
(title, url, content, score), `response_time` and `request_id`.

Everything that comes back is untrusted text. This module records it; it never
acts on it. The API key is read from the environment and is never written
anywhere.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field, HttpUrl

from skuld.core.schemas import SCHEMA_VERSION, SchemaVersion, SkuldModel, UnitInterval

SearchDepth = Literal["basic", "advanced", "fast", "ultra-fast"]


class TavilyHit(SkuldModel):
    title: str
    url: HttpUrl
    content: Annotated[str, Field(max_length=4000)]  # untrusted snippet, stored as data
    score: UnitInterval | None = None


class TavilySearchRecord(SkuldModel):
    """Evidence that a real search happened: timestamps, status, request id, URLs."""

    schema_version: SchemaVersion = SCHEMA_VERSION
    kind: Literal["tavily_search"] = "tavily_search"
    query: Annotated[str, Field(min_length=1)]
    search_depth: SearchDepth
    max_results: Annotated[int, Field(ge=1, le=20)]
    include_domains: list[str] = Field(default_factory=list)
    started_utc: datetime
    finished_utc: datetime
    status: Literal["ok", "empty", "error"]
    request_id: str | None = None
    response_time_s: float | None = None
    result_count: Annotated[int, Field(ge=0)]
    results: list[TavilyHit] = Field(default_factory=list)
    error: str | None = None
    sdk: str = "tavily-python"


class MissingApiKeyError(RuntimeError):
    """Raised instead of pretending a call happened (CLAUDE.md rule 4)."""


def live_search(
    query: str,
    *,
    search_depth: SearchDepth = "basic",
    max_results: int = 5,
    include_domains: list[str] | None = None,
    timeout_s: float = 60.0,
) -> TavilySearchRecord:
    # strip: a CRLF .env or a trailing space would otherwise reach the HTTP header
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise MissingApiKeyError("TAVILY_API_KEY is not set; refusing to fake a search")

    def redact(text: str) -> str:
        """Exceptions can echo the Authorization header; never let the key into evidence."""
        text = text.replace(api_key, "<REDACTED>")
        return re.sub(r"tvly-[A-Za-z0-9_\-]+", "tvly-<REDACTED>", text)

    from importlib.metadata import version as _v

    from tavily import TavilyClient  # imported here so the rest of skuld never needs it

    client = TavilyClient(api_key=api_key)
    kwargs: dict = {"search_depth": search_depth, "max_results": max_results, "timeout": timeout_s}
    if include_domains:
        kwargs["include_domains"] = list(include_domains)
    started = datetime.now(UTC)
    try:
        raw = client.search(query, **kwargs)
    except Exception as e:  # noqa: BLE001 - every failure is recorded, none is a result
        return TavilySearchRecord(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_domains=include_domains or [],
            started_utc=started,
            finished_utc=datetime.now(UTC),
            status="error",
            result_count=0,
            error=redact(f"{type(e).__name__}: {str(e)[:300]}"),
            sdk=f"tavily-python {_v('tavily-python')}",
        )
    finished = datetime.now(UTC)
    hits = []
    for h in raw.get("results") or []:
        try:
            score = h.get("score")
            hits.append(
                TavilyHit(
                    title=str(h.get("title") or "")[:300],
                    url=h["url"],
                    content=str(h.get("content") or "")[:4000],
                    score=None if score is None else max(0.0, min(1.0, float(score))),
                )
            )
        except Exception:  # noqa: BLE001 - a malformed hit is dropped, never trusted
            continue
    return TavilySearchRecord(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        include_domains=include_domains or [],
        started_utc=started,
        finished_utc=finished,
        status="ok" if hits else "empty",
        request_id=raw.get("request_id"),
        response_time_s=raw.get("response_time"),
        result_count=len(hits),
        results=hits,
        sdk=f"tavily-python {_v('tavily-python')}",
    )
