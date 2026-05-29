# AGENTS.md — operating manual for http-archive-mcp

This repo is **primarily driven by AI agents**. Read this before running or changing anything.

## 1. What this is (and isn't)

An MCP server wrapping the public [HTTP Archive Tech Report API](https://github.com/HTTPArchive/tech-report-apis). Exposes web technology adoption, performance, and category data for ~2,500 tracked technologies as MCP tools you can call from Claude Code, Claude Desktop, Cursor, or any MCP client. No auth required; all data is public and read-only, served by `cdn.httparchive.org/v1/`.

It exists to feed **Aglarond research and newsletter studies** ("AI-era search & web visibility") — fast aggregate lookups without leaving the chat. Companion: [`aglarond-techscan`](../aglarond-techscan/) for per-domain lookups on arbitrary lists.

It is **NOT** a hosted service, a customer-facing product, or a write-back tool. It is a thin read-only wrapper.

## 2. Golden rules

- **The API is aggregate-only.** Every endpoint is technology-keyed ("how many sites use X"), NEVER per-domain ("what does example.com use"). Use `aglarond-techscan` or HTTP Archive BigQuery for per-domain.
- **Always be explicit about `rank` (or `geo`) and `client`** in published numbers. "Top 1M / mobile" and "All / desktop" are very different stats; numbers without these qualifiers mislead.
- **Don't bake custom fingerprint detection here.** This MCP wraps HTTP Archive's published reports. Custom detection lives in `aglarond-techscan`.
- **MIT licence, public repo.** Keep it that way unless we explicitly decide to switch.

## 3. Setup

Requires [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
uv run http-archive-mcp     # runs the MCP over stdio
```

Register with a client (e.g. `~/.claude.json` for Claude Code) under `mcpServers`:

```jsonc
{
  "mcpServers": {
    "http-archive": {
      "command": "uv",
      "args": ["--directory", "<path-to>/http-archive-mcp", "run", "http-archive-mcp"]
    }
  }
}
```

Restart the client to surface new tools.

## 4. Tool catalogue (15 tools)

### Discovery — what's available
- `list_categories` — all categories (CMS, Live chat, SEO, ...)
- `list_technologies` — techs in a category or globally; `fields` param surfaces icons/descriptions
- `list_ranks` — `ALL`, `Top 10M`, `Top 1M`, `Top 100k`, `Top 10k`, `Top 1k`
- `list_geos` — geographic regions

### Adoption — who uses what, when
- `get_adoption` — single tech time series
- `compare_adoption` — up to 8 techs side-by-side (with did-you-mean on misses)
- `category_leaderboard` — top N in a category with YoY delta
- `alternatives_for` — peers of a given tech in the same category

### Performance — how sites built with X actually perform
- `get_cwv` — Core Web Vitals (LCP/CLS/INP/TTFB) over time
- `get_cwv_distribution` — CWV pass-rate histograms (the layered "what % pass each metric" detail)
- `get_lighthouse` — Lighthouse category scores over time
- `get_page_weight` — median bytes (total/JS/images)
- `get_audits` — Lighthouse audit pass rates
- `get_geo_breakdown` — CWV snapshot across geos for one metric, top N
- `get_version_distribution` — version-level adoption split

## 5. Which data source for the question

This MCP is one of four data layers. Use the cheapest one that answers the question:

- **"% of the web / top 1M using X" or "X vs Y aggregate trend"** → **this MCP** (HTTP Archive Tech Report). Fast, cached, no auth.
- **"What does THIS specific list of (popular, crawled) domains run?"** → **HTTP Archive BigQuery** (`httparchive.crawl.pages`, `technologies` column, `WHERE root_page IN (...)`). Per-domain on sites in the crawl (~top 16M), monthly-lagged. Respect the cost discipline in the project brief §5.
- **"What does THIS arbitrary / fresh / niche / long-tail list run?"** or **"I need a custom fingerprint"** → [`aglarond-techscan`](../aglarond-techscan/). Live detection on demand.
- **Demand-side data (rankings, SERP features, AI Overview presence)** → DataForSEO (external).

The Tech Report API **cannot** look up a single domain's stack. Don't try.

## 6. Caveats

- **Network dependency.** Tools fail if `cdn.httparchive.org` is unreachable or slow. Default client timeout is 60s.
- **Monthly cadence.** Data updates on HTTP Archive's crawl schedule. Don't expect "yesterday's number."
- **Schema can drift.** HTTP Archive occasionally evolves report endpoints. If a tool starts returning unexpected shapes, check `src/http_archive_mcp/client.py` for the affected endpoint.
- **Smoke test before publishing changes.** `uv run python scripts/smoke.py` exercises every tool against the live API.

## 7. Extending

Adding a new tool:
1. Add the HTTP call in `src/http_archive_mcp/client.py` (or extend an existing helper).
2. Add the `@mcp.tool()`-decorated function in `src/http_archive_mcp/server.py`. Type-hint args; the schema is generated from them.
3. Update `scripts/smoke.py` to call the new tool.
4. Update §4 of this file and the README's tool catalogue.
5. Bump version in `pyproject.toml`.
6. Restart the MCP client to surface the new tool.

Keep the surface minimal — every new tool inflates the system prompt of every consuming agent. Prefer extending an existing tool's params over adding a new one when the underlying data source is the same.
