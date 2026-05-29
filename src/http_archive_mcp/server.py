"""HTTP Archive MCP server.

Wraps the public HTTP Archive Tech Report API
(https://cdn.httparchive.org/v1/) as a set of MCP tools so AI agents can
answer questions about web technology adoption, performance, and trends.

Run via `uv run http-archive-mcp` or `python -m http_archive_mcp`.

Tools (read-only, no auth):
  list_categories            - all category names (or filter to one)
  list_technologies          - all technologies in a category (or globally)
  list_ranks                 - traffic-rank buckets the API supports
  list_geos                  - geographic regions the API supports

  get_adoption               - adoption time-series for a single technology
  compare_adoption           - side-by-side adoption for up to 8 technologies
  category_leaderboard       - top N technologies in a category by latest adoption
  alternatives_for           - other technologies in the same category as X

  get_cwv                    - Core Web Vitals (LCP/CLS/INP/TTFB) over time
  get_cwv_distribution       - share of sites passing CWV at one date (good/NI/poor)
  get_lighthouse             - Lighthouse scores over time
  get_page_weight            - median page weight (total/JS/images) over time
  get_audits                 - Lighthouse audit pass rates over time
  get_geo_breakdown          - latest snapshot across all geographies
  get_version_distribution   - version-level adoption for a technology

Conventions:
  - All responses are JSON-stringified for the MCP transport.
  - `rank` defaults to "Top 1M" (better signal than "ALL" which includes long tail).
  - `geo` defaults to "ALL" (global).
  - Date strings are ISO YYYY-MM-DD or the literal "latest".
  - Each tool returns either a list/dict from the API or a short error string.
"""

from __future__ import annotations

import difflib
import functools
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import client

mcp = FastMCP("http-archive")

DEFAULT_RANK = "Top 1M"
DEFAULT_GEO = "ALL"

# Cached list of all known technology names — populated on first call so we
# can suggest corrections when a caller misspells a tech name.
_KNOWN_TECHS: list[str] | None = None


def _all_tech_names() -> list[str]:
    global _KNOWN_TECHS
    if _KNOWN_TECHS is None:
        try:
            _KNOWN_TECHS = client.technologies(onlyname=True)
        except client.HttpArchiveError:
            _KNOWN_TECHS = []
    return _KNOWN_TECHS or []


def _suggest(name: str, n: int = 5) -> list[str]:
    """Return close matches for `name` from the full tech list."""
    pool = _all_tech_names()
    lower_map = {p.lower(): p for p in pool}
    # First try case-insensitive substring matches (most useful for typos
    # like "rank math" vs "RankMath")
    substr = [p for low, p in lower_map.items() if name.lower() in low or low in name.lower()]
    if substr:
        return substr[:n]
    # Fallback to fuzzy match
    return difflib.get_close_matches(name, pool, n=n, cutoff=0.6)


def _safe(fn):
    """Wrap a tool: catch errors and return a JSON string."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, indent=2, default=str)
        except client.HttpArchiveError as exc:
            return f"HTTP Archive API error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    return wrapper


# ---------------------------------------------------------------------------
# Discovery tools


@mcp.tool()
@_safe
def list_categories(name_only: bool = True) -> Any:
    """List all categories tracked by HTTP Archive (CMS, Live chat, SEO, etc).

    Args:
        name_only: if True (default), return just names; if False, include
                   origin counts and descriptions per category.
    """
    return client.categories(onlyname=name_only)


@mcp.tool()
@_safe
def list_technologies(
    category: str | None = None,
    name_only: bool = True,
    fields: str | None = None,
) -> Any:
    """List technologies, optionally filtered to one category.

    Args:
        category: category name (e.g. "Live chat", "CMS", "WordPress plugins")
        name_only: if True (default), return just names.
        fields: comma-separated columns to include when name_only is False —
                e.g. "technology,category,description,origins,icon". Pass "icon"
                to pull each technology's logo URL (useful for write-ups/sites).
    """
    return client.technologies(category=category, onlyname=name_only, fields=fields)


@mcp.tool()
@_safe
def list_ranks() -> Any:
    """List the traffic-rank buckets the API supports.

    Returns the canonical bucket names usable as the `rank` parameter
    on other tools: ALL, Top 10M, Top 1M, Top 100k, Top 10k, Top 1k.
    """
    return client.ranks()


@mcp.tool()
@_safe
def list_geos() -> Any:
    """List the geographic regions the API supports."""
    return client.geos()


# ---------------------------------------------------------------------------
# Adoption


@mcp.tool()
@_safe
def get_adoption(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    start: str | None = None,
    end: str | None = None,
) -> Any:
    """Adoption time series for a single technology.

    Returns one row per month with `adoption.desktop` and `adoption.mobile`
    origin counts (i.e. how many sites in the rank bucket use this tech).

    Args:
        technology: exact technology name (case-sensitive, e.g. "Intercom")
        rank: traffic bucket, default "Top 1M"
        geo: country / region, default "ALL"
        start: ISO date YYYY-MM-DD, or omit for the API default (~12 months)
        end: ISO date or "latest", or omit
    """
    series = client.adoption(technology=technology, rank=rank, geo=geo, start=start, end=end)
    if not series:
        return {
            "error": f"No data for '{technology}'. Name likely doesn't match HTTP Archive's catalog.",
            "did_you_mean": _suggest(technology),
        }
    return series


@mcp.tool()
@_safe
def compare_adoption(
    technologies: list[str],
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    start: str | None = None,
    end: str | None = None,
) -> Any:
    """Side-by-side adoption time series for multiple technologies.

    Args:
        technologies: list of tech names (up to 8 recommended)
        rank, geo, start, end: same as get_adoption.

    Returns a dict { tech_name: [time_series_rows] } so callers can chart
    each one without separate calls.
    """
    if not technologies:
        return "Provide at least one technology name."
    if len(technologies) > 8:
        return "Too many technologies — pass at most 8."
    out: dict[str, Any] = {}
    for t in technologies:
        series = client.adoption(technology=t, rank=rank, geo=geo, start=start, end=end)
        if not series:
            # Empty result almost always means the tech name doesn't match
            # what HTTP Archive has on file. Suggest corrections.
            suggestions = _suggest(t)
            out[t] = {
                "error": "no data — name likely doesn't match HTTP Archive's catalog",
                "did_you_mean": suggestions,
            }
        else:
            out[t] = series
    return out


def _category_leaderboard(
    category: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    top_n: int = 20,
    months_history: int = 12,
) -> dict:
    """Internal: build a category leaderboard. See `category_leaderboard` tool."""
    from datetime import date, timedelta

    end = date.today().replace(day=1) - timedelta(days=1)
    end_iso = end.replace(day=1).isoformat()
    start_iso = (
        end.replace(day=1) - timedelta(days=int(months_history * 30.5))
    ).replace(day=1).isoformat()

    techs = client.technologies(category=category, onlyname=True)
    rows = []
    for t in techs:
        try:
            series = client.adoption(
                technology=t, rank=rank, geo=geo, start=start_iso, end=end_iso
            )
            if not series:
                continue
            series.sort(key=lambda x: x["date"])
            first, last = series[0], series[-1]
            fd = first["adoption"]["desktop"]
            ld = last["adoption"]["desktop"]
            if ld < 1:
                continue
            yoy_pct = (100 * (ld - fd) / fd) if fd else None
            rows.append(
                {
                    "technology": t,
                    "desktop_latest": ld,
                    "mobile_latest": last["adoption"]["mobile"],
                    "desktop_start": fd,
                    "yoy_pct_desktop": round(yoy_pct, 1) if yoy_pct is not None else None,
                    "latest_date": last["date"],
                    "start_date": first["date"],
                }
            )
        except client.HttpArchiveError:
            continue

    rows.sort(key=lambda r: -r["desktop_latest"])
    return {
        "category": category,
        "rank": rank,
        "geo": geo,
        "rows": rows[:top_n],
    }


@mcp.tool()
@_safe
def category_leaderboard(
    category: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    top_n: int = 20,
    months_history: int = 12,
) -> Any:
    """Top N technologies in a category, ranked by latest desktop adoption.

    For each tech, returns first/last adoption counts and YoY change so the
    table is publication-ready without further processing.

    Args:
        category: category name (e.g. "Live chat", "CMS", "Page builders")
        rank: traffic bucket, default "Top 1M"
        geo: country / region, default "ALL"
        top_n: how many techs to return, default 20
        months_history: how far back to fetch for the YoY delta, default 12
    """
    return _category_leaderboard(category, rank, geo, top_n, months_history)


@mcp.tool()
@_safe
def alternatives_for(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    top_n: int = 10,
) -> Any:
    """Other technologies in the same category as the given technology,
    sorted by latest adoption.

    Args:
        technology: tech name to find peers for
        rank, geo: standard filters
        top_n: how many peers to return, default 10
    """
    info = client.technologies(technology=technology, fields="technology,category")
    if not info:
        return f"Technology not found: {technology}"
    entry = info[0] if isinstance(info, list) else info
    if not isinstance(entry, dict):
        return f"Unexpected API response for {technology}: {entry!r}"
    cats_raw = entry.get("category") or entry.get("categories")
    if not cats_raw:
        return f"No category info for {technology}"
    # API returns categories as comma-separated string, e.g. "CRM, Live chat"
    if isinstance(cats_raw, str):
        cat_list = [c.strip() for c in cats_raw.split(",") if c.strip()]
    elif isinstance(cats_raw, list):
        cat_list = cats_raw
    else:
        cat_list = [str(cats_raw)]
    category = cat_list[0] if cat_list else None
    if not category:
        return f"No category info for {technology}"

    board = _category_leaderboard(category=category, rank=rank, geo=geo, top_n=top_n + 1)
    rows = [
        r for r in board.get("rows", [])
        if r["technology"].lower() != technology.lower()
    ]
    return {
        "technology": technology,
        "category": category,
        "alternatives": rows[:top_n],
    }


# ---------------------------------------------------------------------------
# Performance


@mcp.tool()
@_safe
def get_cwv(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    start: str | None = None,
    end: str | None = None,
) -> Any:
    """Core Web Vitals (LCP, CLS, INP, TTFB) over time for a technology."""
    return client.cwv(technology=technology, rank=rank, geo=geo, start=start, end=end)


@mcp.tool()
@_safe
def get_cwv_distribution(
    technology: str,
    date: str,
    rank: str = "ALL",
    geo: str = DEFAULT_GEO,
) -> Any:
    """Core Web Vitals distribution histogram for a technology at one date.

    Unlike `get_cwv` (median metrics over time), this returns per-bucket
    histograms — the count of origins whose p75 falls in each LCP/INP/CLS/
    FCP/TTFB bucket — so you can compute the *share of sites passing* CWV.
    Ideal for head-to-head snapshots (e.g. "% of Shopify vs WooCommerce
    sites passing Core Web Vitals").

    Args:
        technology: exact technology name (e.g. "WordPress"); the API also
            accepts a comma-separated list (e.g. "Wix,WordPress").
        date: ISO month YYYY-MM-DD (e.g. "2026-02-01") — required; a
            point-in-time snapshot, not a series. This report lags the raw
            crawl, so the most recent month or two may return [].
        rank: NUMERIC rank ceiling as a string — e.g. "100000" (top 100k),
            "10000" (top 10k). This endpoint is the exception: it does NOT
            accept the "Top 1M" bucket names other tools use (those return
            zero rows). Default "ALL" = all ranks.
        geo: country / region, default "ALL" (e.g. "United States of America").
    """
    return client.cwv_distribution(technology=technology, date=date, rank=rank, geo=geo)


@mcp.tool()
@_safe
def get_lighthouse(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    start: str | None = None,
    end: str | None = None,
) -> Any:
    """Lighthouse category scores (perf, a11y, SEO, best practices) over time."""
    return client.lighthouse(technology=technology, rank=rank, geo=geo, start=start, end=end)


@mcp.tool()
@_safe
def get_page_weight(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
    start: str | None = None,
    end: str | None = None,
) -> Any:
    """Median page weight (total/JS/images bytes) over time for a technology."""
    return client.page_weight(technology=technology, rank=rank, geo=geo, start=start, end=end)


@mcp.tool()
@_safe
def get_audits(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
) -> Any:
    """Lighthouse audit pass rates for a technology (latest available date).

    Note: the upstream HTTP Archive `/audits` endpoint currently returns HTTP 500
    when start/end dates are passed, so this tool intentionally omits them and
    returns whatever the API gives back (typically the latest crawl).
    """
    return client.audits(technology=technology, rank=rank, geo=geo)


@mcp.tool()
@_safe
def get_geo_breakdown(
    technology: str,
    metric: str = "overall",
    top_n: int = 25,
    rank: str = DEFAULT_RANK,
    end: str | None = None,
) -> Any:
    """CWV snapshot across geographies for one technology at one date.

    The raw API response is huge (~237 geos × 7 vitals × desktop+mobile),
    so this tool filters server-side to one metric and the top N geos by
    sample size. Pass metric="ALL" to get every vital (still trimmed by top_n).

    Args:
        technology: tech name (e.g. "WordPress")
        metric: one of "overall", "LCP", "CLS", "INP", "TTFB", "FCP", "FID", or "ALL"
        top_n: how many geos to return, sorted by mobile sample size (default 25)
        rank: traffic bucket
        end: ISO date or "latest"
    """
    raw = client.geo_breakdown(technology=technology, rank=rank, end=end)
    if not raw:
        return raw

    # Some shapes the API returns: a list of {geo, vitals: [...]} or similar.
    # Normalize to a list of dicts and trim each row.
    if not isinstance(raw, list):
        return raw

    metric_upper = metric.upper() if metric.upper() != "ALL" else None
    rows = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        vitals = r.get("vitals") or r.get("metrics") or []
        if metric_upper:
            vitals = [
                v for v in vitals
                if isinstance(v, dict) and (v.get("name") or "").upper() == metric_upper
            ]
        new_row = dict(r)
        new_row["vitals"] = vitals
        # Score: total mobile sample size across kept vitals (or 0)
        score = 0
        for v in vitals:
            mobile = v.get("mobile") or {}
            score = max(score, mobile.get("tested") or 0)
        new_row["_sample_score"] = score
        rows.append(new_row)

    rows.sort(key=lambda x: -x.get("_sample_score", 0))
    rows = rows[:top_n]
    for r in rows:
        r.pop("_sample_score", None)
    return {
        "technology": technology,
        "metric": metric,
        "rank": rank,
        "rows": rows,
    }


@mcp.tool()
@_safe
def get_version_distribution(
    technology: str,
    rank: str = DEFAULT_RANK,
    geo: str = DEFAULT_GEO,
) -> Any:
    """Version-level adoption distribution for a technology (e.g. WordPress 6.5 vs 6.4)."""
    return client.versions(technology=technology)


# ---------------------------------------------------------------------------
# Entrypoint


def main() -> None:
    mcp.run()
