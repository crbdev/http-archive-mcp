"""Smoke test: exercise each tool against the real HTTP Archive API.

Run: `uv run python scripts/smoke.py`
"""

from __future__ import annotations

import json
import sys

from http_archive_mcp import client
from http_archive_mcp.server import (
    _category_leaderboard,
    _suggest,
    alternatives_for,
    compare_adoption,
    get_adoption,
    get_audits,
    get_geo_breakdown,
)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def show(obj, n=6):
    if isinstance(obj, list):
        print(f"  [{len(obj)} items]")
        for x in obj[:n]:
            print(f"    {x}")
        if len(obj) > n:
            print(f"    ... +{len(obj) - n} more")
    elif isinstance(obj, dict):
        text = json.dumps(obj, indent=2, default=str)
        if len(text) > 1200:
            text = text[:1200] + "\n    ... [truncated]"
        print(text)
    else:
        s = str(obj)
        if len(s) > 1200:
            s = s[:1200] + " ... [truncated]"
        print(f"  {s}")


def call_tool(fn, **kwargs):
    """Invoke an MCP-decorated tool by going through its registered function."""
    # FastMCP wraps the function; the underlying impl is at .fn (older) or
    # accessible by direct call. We simply call .__wrapped__ chain or just
    # use a fresh route: since our tools are also exported plain Python
    # functions when imported, calling them returns the JSON string.
    return fn(**kwargs)


def main() -> int:
    try:
        section("list_categories")
        cats = client.categories(onlyname=True)
        show(cats, n=10)

        section("list_technologies in 'Live chat'")
        techs = client.technologies(category="Live chat", onlyname=True)
        show(techs, n=5)
        assert "Intercom" in techs

        section("get_adoption: WordPress (valid)")
        out = get_adoption(technology="WordPress", rank="Top 1M",
                          start="2026-03-01", end="2026-04-01")
        show(out)
        assert "error" not in (out if isinstance(out, str) else "")

        section("get_adoption: 'wordpres' (typo — should suggest)")
        out = get_adoption(technology="wordpres", rank="Top 1M")
        show(out)
        parsed = json.loads(out) if isinstance(out, str) else out
        assert isinstance(parsed, dict) and "did_you_mean" in parsed, "Expected suggestion list"
        print("  -> suggestions:", parsed["did_you_mean"])

        section("compare_adoption: mix of valid + invalid names")
        out = compare_adoption(
            technologies=["Yoast SEO", "Rank Math", "All in One SEO Pack"],
            rank="Top 1M", start="2026-03-01", end="2026-04-01"
        )
        show(out)
        parsed = json.loads(out) if isinstance(out, str) else out
        assert isinstance(parsed["Yoast SEO"], list) and parsed["Yoast SEO"], "Yoast should have data"
        assert "did_you_mean" in parsed["Rank Math"], "Rank Math should get a suggestion"
        print("  -> suggestions for 'Rank Math':", parsed["Rank Math"]["did_you_mean"])

        section("alternatives_for: Intercom (was broken in v0.1)")
        out = alternatives_for(technology="Intercom", rank="Top 1M", top_n=5)
        show(out)
        parsed = json.loads(out) if isinstance(out, str) else out
        assert isinstance(parsed, dict) and parsed.get("alternatives"), "Expected alternatives list"

        section("category_leaderboard: 'Page builders' top 5")
        out = _category_leaderboard(category="Page builders", rank="Top 1M", top_n=5)
        print(json.dumps(out, indent=2, default=str))

        section("get_audits: WordPress (no dates — upstream broken with them)")
        out = get_audits(technology="WordPress", rank="Top 1M")
        show(out)

        section("get_geo_breakdown: WordPress, LCP only, top 5 geos")
        out = get_geo_breakdown(technology="WordPress", metric="LCP", top_n=5)
        show(out)
        parsed = json.loads(out) if isinstance(out, str) else out
        assert isinstance(parsed, dict) and "rows" in parsed
        assert len(parsed["rows"]) <= 5

        section("_suggest helper: 'wordpres'")
        print(" ", _suggest("wordpres"))

        print("\nAll smoke checks passed.")
        return 0
    except AssertionError as exc:
        print(f"\nFAIL: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
