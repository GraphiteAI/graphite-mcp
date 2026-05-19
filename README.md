# graphite-mcp

MCP server for the **[Graphite Financial Knowledge Graph](https://graph.graphite-ai.net)** — wires the graph into Claude Code, Claude Desktop, Cursor, Codex CLI, and any other MCP-compatible client.

Your Claude / agent does the reasoning. Graphite answers the graph questions it asks for. **No LLM tokens are billed by Graphite** — you bring your own LLM (subscription or API key); we only serve graph data.

## Install

```bash
pip install graphite-mcp
```

Or from source:

```bash
git clone https://github.com/Sherwin-Graphite/graphite-mcp.git
cd graphite-mcp
pip install -e .
```

## Get a Graphite key

Free tier — **100 graph queries / month** — at:
**https://graph.graphite-ai.net/#/portal**

Sign up with your email; you get back a key like `sk-…`.

Chat-with-the-graph in the web portal is BYOK — you bring your own
Anthropic or OpenAI key (it stays in your browser). Or skip the portal and
use this MCP server with your Claude / ChatGPT subscription, no API key
needed on the LLM side at all.

## Configure your client

Same JSON shape works for every MCP client; only the file path differs.

```json
{
  "mcpServers": {
    "graphite": {
      "command": "graphite-mcp",
      "env": {
        "CENTRAL_SERVER_URL": "https://api.graphite-ai.net",
        "CUSTOMER_API_KEY": "sk-your-graphite-key"
      }
    }
  }
}
```

| Client          | Config path |
| --------------- | --- |
| Claude Code     | `~/.claude/mcp.json` |
| Claude Desktop  | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| Cursor          | `~/.cursor/mcp.json` |
| Codex CLI       | `~/.codex/config.json` |

Restart your client after editing.

If you installed from source and don't want to put the package on PATH, replace the `command` line with:

```json
"command": "python",
"args": ["-m", "graphite_mcp"],
```

## Available tools

Once configured, Claude can call these tools to answer questions about companies, supply chains, executives, regulations, and patents.

| Tool | Purpose |
| --- | --- |
| `search_entities`   | Free-text search by name, ticker, sector, or description |
| `get_entity`        | Full record for one entity by ID (e.g. `company:NVDA`) |
| `get_relationships` | Every edge attached to an entity (employs, supplies, depends_on, …) |
| `get_facts`         | Typed fact log for an entity (revenue, headcount, etc.) |
| `find_path`         | Shortest path between two entities through the graph |
| `exposure_analysis` | 1st + 2nd-degree neighborhood, sector breakdown — supply-chain risk view |
| `compare_entities`  | Shared connections + path distance + direct relationships between two |

## Example prompts

After setup, just ask Claude:

- "What's NVIDIA's supply-chain exposure to TSMC?"
- "Find the shortest path from company:AAPL to company:ASML."
- "Compare Microsoft and Google — who do they share board members with?"
- "List every revenue-from edge for NVDA."

Claude will pick the right tool, call this MCP server, and ground its answer in real graph data.

## How it works

```
your Claude          graphite-mcp           api.graphite-ai.net
─────────────       ────────────────       ─────────────────────
"NVDA exposure?" ─→ exposure_analysis ─→  GET /graph/exposure
                    (this package)         (returns JSON)
                                       ←─
              ←─    formatted answer
```

The MCP server is a thin stdio adapter — it doesn't store anything, doesn't see your prompts, doesn't bill you. All the value lives in the graph at `api.graphite-ai.net`.

## Env vars

| Var | Default | Notes |
| --- | --- | --- |
| `CENTRAL_SERVER_URL` | `http://localhost:8000` | Override to use a different Graphite deployment |
| `CUSTOMER_API_KEY`   | (empty) | Required — issued at https://graph.graphite-ai.net/#/portal |

## License

MIT. Use freely, modify freely, no warranty.
