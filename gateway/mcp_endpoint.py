import asyncio
import time

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from auth import authenticate
from db import get_conn
from upstream import call_tool, list_all_tools, root_error

router = APIRouter()

SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
CALL_TIMEOUT = 15.0  # seconds to wait for one tool call


def rpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def text_error(text):
    return {"content": [{"type": "text", "text": text}], "isError": True}


def audit(user_name, server, tool, duration_ms, outcome, detail=None):
    # Arguments are never logged: they can contain customer data.
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_name, server, tool, duration_ms, outcome, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_name, server, tool, duration_ms, outcome, detail),
        )


def enabled_servers():
    with get_conn() as conn:
        rows = conn.execute("SELECT name, url FROM mcp_servers WHERE enabled = 1 ORDER BY id").fetchall()
    return [dict(r) for r in rows]


async def handle(msg: dict, user: dict):
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return rpc_result(msg_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "mcp-gateway", "version": "0.1.0"},
        })

    if method == "ping":
        return rpc_result(msg_id, {})

    if method == "tools/list":
        tools, _ = await list_all_tools(enabled_servers())
        return rpc_result(msg_id, {"tools": [
            {"name": t["name"], "description": t["description"] or "", "inputSchema": t["inputSchema"]}
            for t in tools
        ]})

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return rpc_error(msg_id, -32602, "arguments must be an object")

        server_name, sep, tool = name.partition("__")
        servers = {s["name"]: s for s in enabled_servers()}
        if not sep or not tool or server_name not in servers:
            audit(user["name"], server_name or None, name, 0, "unknown_tool")
            return rpc_error(msg_id, -32602, f"Unknown tool '{name}'")

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                call_tool(servers[server_name]["url"], tool, arguments), timeout=CALL_TIMEOUT
            )
        except asyncio.TimeoutError:
            ms = int((time.monotonic() - start) * 1000)
            audit(user["name"], server_name, tool, ms, "timeout", f"no response in {CALL_TIMEOUT:.0f}s")
            return rpc_result(msg_id, text_error(
                f"Server '{server_name}' did not respond within {CALL_TIMEOUT:.0f} seconds."))
        except Exception as exc:
            ms = int((time.monotonic() - start) * 1000)
            audit(user["name"], server_name, tool, ms, "unreachable", root_error(exc))
            return rpc_result(msg_id, text_error(f"Server '{server_name}' is unavailable."))

        ms = int((time.monotonic() - start) * 1000)
        audit(user["name"], server_name, tool, ms, "error" if result.isError else "ok")
        return rpc_result(msg_id, {
            "content": [c.model_dump(mode="json", exclude_none=True) for c in result.content],
            "isError": bool(result.isError),
        })

    return rpc_error(msg_id, -32601, f"Method not found: {method}")


@router.post("/mcp")
async def mcp_post(request: Request, user: dict = Depends(authenticate)):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(rpc_error(None, -32700, "Parse error"), status_code=400)

    messages = body if isinstance(body, list) else [body]
    responses = []
    for msg in messages:
        if isinstance(msg, dict) and "method" in msg and "id" in msg:
            responses.append(await handle(msg, user))
        # notifications (no id) get no reply
    if not responses:
        return Response(status_code=202)
    return JSONResponse(responses if isinstance(body, list) else responses[0])


@router.get("/mcp")
async def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})
