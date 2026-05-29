"""Thin HTTP client for the HTTP Archive Tech Report API.

The API is public, read-only, no auth required, CORS-enabled.
Host: https://cdn.httparchive.org/v1/
Docs: https://github.com/HTTPArchive/tech-report-apis

All endpoints return JSON. Most accept a `fields` parameter to project a
subset of columns; we don't use that here because the responses are already
small enough to pass through verbatim.

Conventions for query parameters across multiple endpoints:
  technology   single tech name (case-sensitive, exact match)
  category     single category name
  rank         one of: ALL, Top 10M, Top 1M, Top 100k, Top 10k, Top 1k
  geo          country / region name (use "ALL" for global)
  start, end   ISO date YYYY-MM-DD; or the literal "latest"
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE = "https://cdn.httparchive.org/v1"
# Some analytical endpoints (cwv-distribution, geo-breakdown) run heavy
# uncached queries that can take 15-30s+ on a cold cache, so allow headroom.
DEFAULT_TIMEOUT = 60.0


class HttpArchiveError(RuntimeError):
    """Raised when the HTTP Archive API returns a non-2xx response."""


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET an API path, return parsed JSON.

    Drops None values from params so callers can pass optional args inline.
    """
    cleaned = {k: v for k, v in (params or {}).items() if v is not None}
    url = f"{API_BASE}{path}"
    try:
        r = httpx.get(url, params=cleaned, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        raise HttpArchiveError(
            f"HTTP {exc.response.status_code} from {exc.request.url}: {exc.response.text[:300]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise HttpArchiveError(f"Network error calling {url}: {exc}") from exc


# ----------------------------------------------------------------------------
# Endpoint wrappers — one function per API route.


def categories(category: str | None = None, onlyname: bool = False) -> Any:
    return _get("/categories", {"category": category, "onlyname": str(onlyname).lower()})


def technologies(
    technology: str | None = None,
    category: str | None = None,
    onlyname: bool = False,
    fields: str | None = None,
) -> Any:
    # `onlyname=true` returns a flat list of names.
    # `onlyname=false` is silently ignored by the API, so to get more than
    # names we have to explicitly request fields via the `fields` param.
    params: dict[str, Any] = {"technology": technology, "category": category}
    if onlyname:
        params["onlyname"] = "true"
    elif fields is None:
        fields = "technology,category,description,origins"
    if fields:
        params["fields"] = fields
    return _get("/technologies", params)


def versions(
    technology: str | None = None,
    category: str | None = None,
    version: str | None = None,
    onlyname: bool = False,
) -> Any:
    return _get(
        "/versions",
        {
            "technology": technology,
            "category": category,
            "version": version,
            "onlyname": str(onlyname).lower(),
        },
    )


def adoption(
    technology: str | None = None,
    geo: str = "ALL",
    rank: str = "ALL",
    start: str | None = None,
    end: str | None = None,
) -> Any:
    return _get(
        "/adoption",
        {"technology": technology, "geo": geo, "rank": rank, "start": start, "end": end},
    )


def cwv(
    technology: str | None = None,
    geo: str = "ALL",
    rank: str = "ALL",
    start: str | None = None,
    end: str | None = None,
) -> Any:
    return _get(
        "/cwv",
        {"technology": technology, "geo": geo, "rank": rank, "start": start, "end": end},
    )


def cwv_distribution(
    technology: str,
    date: str,
    geo: str = "ALL",
    rank: str = "ALL",
) -> Any:
    return _get(
        "/cwv-distribution",
        {"technology": technology, "date": date, "geo": geo, "rank": rank},
    )


def lighthouse(
    technology: str | None = None,
    geo: str = "ALL",
    rank: str = "ALL",
    start: str | None = None,
    end: str | None = None,
) -> Any:
    return _get(
        "/lighthouse",
        {"technology": technology, "geo": geo, "rank": rank, "start": start, "end": end},
    )


def page_weight(
    technology: str | None = None,
    geo: str = "ALL",
    rank: str = "ALL",
    start: str | None = None,
    end: str | None = None,
) -> Any:
    return _get(
        "/page-weight",
        {"technology": technology, "geo": geo, "rank": rank, "start": start, "end": end},
    )


def audits(
    technology: str | None = None,
    geo: str = "ALL",
    rank: str = "ALL",
    start: str | None = None,
    end: str | None = None,
) -> Any:
    return _get(
        "/audits",
        {"technology": technology, "geo": geo, "rank": rank, "start": start, "end": end},
    )


def geo_breakdown(
    technology: str,
    rank: str = "ALL",
    end: str | None = None,
) -> Any:
    return _get(
        "/geo-breakdown",
        {"technology": technology, "rank": rank, "end": end},
    )


def ranks() -> Any:
    return _get("/ranks")


def geos() -> Any:
    return _get("/geos")
