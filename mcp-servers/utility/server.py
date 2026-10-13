from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("utility", host="0.0.0.0", port=8000)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@mcp.tool()
def get_current_time(timezone: str = "Asia/Kolkata") -> dict:
    """Get the current date and time in an IANA timezone, e.g. Asia/Kolkata or UTC."""
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"Unknown timezone '{timezone}'. Example: Asia/Kolkata") from None
    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "iso": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
    }


@mcp.tool()
def add_gst(amount_inr: float, gst_percent: float = 18.0) -> dict:
    """Add GST to an amount in Indian Rupees (INR). Default GST is 18 percent."""
    if amount_inr < 0 or gst_percent < 0:
        raise ValueError("amount_inr and gst_percent must not be negative")
    gst = round(amount_inr * gst_percent / 100, 2)
    return {
        "amount_inr": amount_inr,
        "gst_percent": gst_percent,
        "gst_inr": gst,
        "total_inr": round(amount_inr + gst, 2),
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
