"""MCP server for the Graphite Financial Knowledge Graph.

Exposes 7 tools that any MCP-compatible LLM client (Claude Code, Claude
Desktop, Cursor, Codex CLI, etc.) can call. Each tool is a thin wrapper
around the public REST API at api.graphite-ai.net — nothing is computed
locally, nothing is cached, nothing is billed by this process.

Configuration is via env vars (set in your client's MCP config block):
    CENTRAL_SERVER_URL = https://api.graphite-ai.net   (or self-hosted)
    CUSTOMER_API_KEY   = sk-...                         (required)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

CENTRAL_SERVER_URL = os.getenv("CENTRAL_SERVER_URL", "http://localhost:8000")
CUSTOMER_API_KEY = os.getenv("CUSTOMER_API_KEY", "")

server = Server("graphite-mcp")


def _headers() -> dict:
    return {"X-API-Key": CUSTOMER_API_KEY}


def _url(path: str) -> str:
    return f"{CENTRAL_SERVER_URL.rstrip('/')}/api/v1{path}"


async def _get(path: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_url(path), params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


# ──────────────────── tool definitions ────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_entities",
            description="Search the financial knowledge graph for companies, people, patents by name, ticker, or description. Example: search_entities(query='NVIDIA') or search_entities(query='semiconductor', sector='semiconductors')",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (name, ticker, or keyword)"},
                    "entity_type": {"type": "string", "description": "Filter by type", "enum": ["company", "person", "patent", "product", "regulation", "event"]},
                    "sector": {"type": "string", "description": "Filter by sector: semiconductors, software, pharma, etc."},
                    "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_entity",
            description="Get detailed information about a specific entity by ID. Example: get_entity(entity_id='company:NVDA')",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID, e.g. 'company:AAPL', 'person:TIM_COOK_AAPL'"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="get_relationships",
            description="Get all relationships for an entity — suppliers, competitors, partners, dependencies, etc. Example: get_relationships(entity_id='company:NVDA')",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="get_facts",
            description="Get known facts about an entity — revenue, employee count, etc. Example: get_facts(entity_id='company:AAPL')",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="find_path",
            description="Find how two companies/entities are connected through the knowledge graph. Shows the chain of relationships. Example: find_path(source='company:AAPL', target='company:TSM')",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source entity ID"},
                    "target": {"type": "string", "description": "Target entity ID"},
                    "max_depth": {"type": "integer", "description": "Max hops (default 6)", "default": 6},
                },
                "required": ["source", "target"],
            },
        ),
        Tool(
            name="exposure_analysis",
            description="Analyze a company's exposure: 1st and 2nd degree connections, sector concentration, dependency risks. Example: exposure_analysis(entity_id='company:TSM')",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID to analyze"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="compare_entities",
            description="Compare two entities: shared connections, direct relationships, path distance. Example: compare_entities(entity_a='company:NVDA', entity_b='company:AMD')",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_a": {"type": "string", "description": "First entity ID"},
                    "entity_b": {"type": "string", "description": "Second entity ID"},
                },
                "required": ["entity_a", "entity_b"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if not CUSTOMER_API_KEY:
        return [TextContent(
            type="text",
            text="No CUSTOMER_API_KEY set. Get one at https://graph.graphite-ai.net/#/portal "
                 "and add it to the env block of your MCP config.",
        )]
    try:
        if name == "search_entities":
            result = await _get("/search", params={
                "q": arguments["query"],
                "type": arguments.get("entity_type"),
                "sector": arguments.get("sector"),
                "limit": arguments.get("limit", 20),
            })

        elif name == "get_entity":
            result = await _get(f"/entities/{arguments['entity_id']}")

        elif name == "get_relationships":
            result = await _get(f"/entities/{arguments['entity_id']}/relationships")

        elif name == "get_facts":
            result = await _get(f"/entities/{arguments['entity_id']}/facts")

        elif name == "find_path":
            result = await _get("/graph/path", params={
                "source": arguments["source"],
                "target": arguments["target"],
                "max_depth": arguments.get("max_depth", 6),
            })

        elif name == "exposure_analysis":
            result = await _get("/graph/exposure", params={
                "entity": arguments["entity_id"],
            })

        elif name == "compare_entities":
            result = await _get("/graph/compare", params={
                "a": arguments["entity_a"],
                "b": arguments["entity_b"],
            })

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except httpx.HTTPStatusError as e:
        # Surface the central server's error message verbatim — most useful
        # for the LLM to see when an entity_id is wrong or quota is hit.
        try:
            body = e.response.json()
            detail = body.get("detail", e.response.text)
        except Exception:
            detail = e.response.text
        return [TextContent(
            type="text",
            text=f"API error ({e.response.status_code}): {detail}",
        )]
    except Exception as e:  # noqa: BLE001
        return [TextContent(type="text", text=f"Error: {e}")]


async def run():
    # Stdio: the MCP client (Claude Code etc.) speaks JSON-RPC over our
    # stdin/stdout. Anything we print() goes to stderr instead.
    print(
        f"graphite-mcp ▸ {CENTRAL_SERVER_URL}  "
        f"(key {'set' if CUSTOMER_API_KEY else 'MISSING'})",
        file=sys.stderr,
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
