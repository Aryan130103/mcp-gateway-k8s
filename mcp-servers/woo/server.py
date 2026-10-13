import os

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# All settings come from the environment, never from code.
BASE_URL = os.environ.get("WOO_BASE_URL", "http://wordpress:80")
CONSUMER_KEY = os.environ["WOO_CONSUMER_KEY"]
CONSUMER_SECRET = os.environ["WOO_CONSUMER_SECRET"]

ORDER_STATUSES = {
    "pending", "processing", "on-hold", "completed",
    "cancelled", "refunded", "failed",
}

mcp = FastMCP("woo", host="0.0.0.0", port=8000)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")

client = httpx.Client(
    base_url=BASE_URL,
    auth=(CONSUMER_KEY, CONSUMER_SECRET),
    # Traffic stays inside the cluster over plain HTTP; this header tells
    # WooCommerce to accept the API key as if the request were HTTPS.
    headers={"X-Forwarded-Proto": "https"},
    timeout=10.0,
)


def woo(method: str, path: str, params: dict | None = None, body: dict | None = None):
    """Call the WooCommerce REST API and turn failures into short, safe errors."""
    try:
        response = client.request(method, f"/wp-json/wc/v3{path}", params=params, json=body)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("message", "")
        except Exception:
            detail = ""
        raise ValueError(f"Store returned {exc.response.status_code}: {detail}") from None
    except httpx.RequestError as exc:
        raise ValueError(f"Could not reach the store ({type(exc).__name__})") from None
    return response.json()


def order_summary(o: dict) -> dict:
    billing = o.get("billing", {})
    return {
        "id": o["id"],
        "status": o["status"],
        "total": o["total"],
        "currency": o["currency"],
        "date_created": o["date_created"],
        "customer": f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
        "items": [{"name": i["name"], "quantity": i["quantity"]} for i in o.get("line_items", [])],
    }


@mcp.tool()
def list_products(search: str = "", per_page: int = 10) -> list[dict]:
    """List products in the store (prices are in Indian Rupees, INR).

    Use `search` to filter by product name. `per_page` is capped at 50.
    """
    params = {"per_page": max(1, min(per_page, 50))}
    if search:
        params["search"] = search
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "price": p["price"],
            "status": p["status"],
            "stock_status": p["stock_status"],
        }
        for p in woo("GET", "/products", params)
    ]


@mcp.tool()
def create_product(name: str, price: float, description: str = "") -> dict:
    """Create a simple product. `price` is in Indian Rupees (INR) and must not be negative."""
    if not name.strip():
        raise ValueError("name must not be empty")
    if price < 0:
        raise ValueError("price must not be negative")
    body = {
        "name": name.strip(),
        "type": "simple",
        "regular_price": str(price),
        "description": description,
    }
    p = woo("POST", "/products", body=body)
    return {"id": p["id"], "name": p["name"], "price": p["price"], "status": p["status"]}


@mcp.tool()
def list_orders(
    status: str = "any", after: str = "", before: str = "", per_page: int = 10
) -> list[dict]:
    """List orders, newest first.

    `status` is one of: any, pending, processing, on-hold, completed, cancelled,
    refunded, failed. `after` and `before` are ISO 8601 date-times such as
    2026-10-12T00:00:00 (use `after` for "orders since this moment", e.g. today's
    orders). `per_page` is capped at 50.
    """
    if status != "any" and status not in ORDER_STATUSES:
        raise ValueError(f"status must be 'any' or one of {sorted(ORDER_STATUSES)}")
    params = {
        "per_page": max(1, min(per_page, 50)),
        "orderby": "date",
        "order": "desc",
        "status": status,
    }
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    return [order_summary(o) for o in woo("GET", "/orders", params)]


@mcp.tool()
def get_order(order_id: int) -> dict:
    """Get one order by its id, including items, payment method and customer city."""
    o = woo("GET", f"/orders/{order_id}")
    detail = order_summary(o)
    detail["payment_method"] = o.get("payment_method_title", "")
    detail["city"] = o.get("billing", {}).get("city", "")
    detail["items"] = [
        {"name": i["name"], "quantity": i["quantity"], "total": i["total"]}
        for i in o.get("line_items", [])
    ]
    return detail


@mcp.tool()
def update_order_status(order_id: int, status: str) -> dict:
    """Change an order's status. `status` is one of: pending, processing, on-hold,
    completed, cancelled, refunded, failed."""
    if status not in ORDER_STATUSES:
        raise ValueError(f"status must be one of {sorted(ORDER_STATUSES)}")
    o = woo("PUT", f"/orders/{order_id}", body={"status": status})
    return {"id": o["id"], "status": o["status"]}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
