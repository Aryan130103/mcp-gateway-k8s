import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

LIST_TIMEOUT = 5.0  # seconds to wait for one server's tool list


async def fetch_tools(url: str) -> list:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return list(result.tools)


async def list_all_tools(servers: list[dict]) -> tuple[list[dict], list[dict]]:
    """Ask every server in parallel. A failing server is reported, never fatal."""

    async def one(server: dict):
        try:
            tools = await asyncio.wait_for(fetch_tools(server["url"]), timeout=LIST_TIMEOUT)
            return server["name"], "ok", tools, None
        except asyncio.TimeoutError:
            return server["name"], "unreachable", [], "timed out"
        except Exception as exc:  # report the type only, never raw upstream details
            return server["name"], "unreachable", [], type(exc).__name__

    results = await asyncio.gather(*(one(s) for s in servers))

    tools_out: list[dict] = []
    status_out: list[dict] = []
    for name, status, tools, error in results:
        status_out.append({"server": name, "status": status, "tool_count": len(tools), "error": error})
        for t in tools:
            tools_out.append(
                {
                    "name": f"{name}__{t.name}",
                    "server": name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
            )
    return tools_out, status_out
