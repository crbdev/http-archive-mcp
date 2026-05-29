# http-archive-mcp

An [MCP](https://modelcontextprotocol.io/) server wrapping the public [HTTP Archive Tech Report API](https://github.com/HTTPArchive/tech-report-apis). Exposes web technology adoption, performance, and category data for ~2,500 tracked technologies as MCP tools you can call from Claude Code, Claude Desktop, Cursor, or any other MCP client.

No auth required. All data is public and read-only, served by `https://cdn.httparchive.org/v1/`.

## What you can ask

- "What chat tools are growing fastest in the top 1M sites?"
- "Compare Yoast SEO and RankMath adoption."
- "What are the alternatives to Drift?"
- "How is WordPress's Core Web Vitals trending?"
- "What's the version distribution of WordPress in the wild?"

## Tools

**Discovery**
- `list_categories` — all category names (CMS, Live chat, SEO, etc.)
- `list_technologies` — all techs in a category (or globally)
- `list_ranks` — traffic-rank buckets (ALL, Top 10M, Top 1M, Top 100k, Top 10k, Top 1k)
- `list_geos` — geographic regions

**Adoption**
- `get_adoption` — adoption time series for one tech
- `compare_adoption` — side-by-side for up to 8 techs (with did-you-mean on misses)
- `category_leaderboard` — top N in a category with YoY delta
- `alternatives_for` — peers of a given tech in the same category

**Performance**
- `get_cwv` — Core Web Vitals (LCP/CLS/INP/TTFB) over time
- `get_lighthouse` — Lighthouse category scores over time
- `get_page_weight` — median bytes (total/JS/images)
- `get_audits` — Lighthouse audit pass rates
- `get_geo_breakdown` — CWV snapshot across geos, filtered by metric + top N
- `get_version_distribution` — version-level adoption

## Install locally

Requires [`uv`](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/aglarondai/http-archive-mcp.git
cd http-archive-mcp
uv sync
```

## Run

```sh
uv run http-archive-mcp
```

## Register with Claude Code / Claude Desktop / Cursor

Add this to your MCP client config (e.g. `~/.claude.json` for Claude Code) under `mcpServers`:

```json
"http-archive": {
  "command": "uv",
  "args": [
    "--directory", "<path-to>/http-archive-mcp",
    "run", "http-archive-mcp"
  ]
}
```

Restart your MCP client to pick it up.

## Smoke test

```sh
uv run python scripts/smoke.py
```

Exercises every tool against the live HTTP Archive API.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Built on [HTTP Archive](https://httparchive.org/)'s freely-available Tech Report API. All web technology data is theirs; this project just wraps the API as MCP tools.
