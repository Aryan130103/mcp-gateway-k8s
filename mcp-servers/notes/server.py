from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("notes", host="0.0.0.0", port=8000)
NOTES: list[dict] = []


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@mcp.tool()
def add_note(text: str) -> dict:
    """Save a short note (max 500 characters). Notes are kept in memory and
    reset when the server restarts."""
    if not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > 500:
        raise ValueError("text must be 500 characters or fewer")
    note = {
        "id": len(NOTES) + 1,
        "text": text.strip(),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    NOTES.append(note)
    return note


@mcp.tool()
def list_notes() -> list[dict]:
    """List all saved notes, newest first."""
    return list(reversed(NOTES))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
