# System design and tradeoffs

## Architecture
```
client / dashboard chat -> Traefik -> gateway -> woo-mcp -> WordPress -> MariaDB
                                          |-> notes-mcp
                                          '-> utility-mcp
```

Everything lives in the `mcp-gateway` namespace. Public: shop, dashboard, gateway (each through an Ingress). Internal only: the three MCP servers and MariaDB (ClusterIP Services, no Ingress, plus NetworkPolicies).

| Piece | Role |
|---|---|
| Store chart | WordPress + WooCommerce + MariaDB, PVCs, a Helm-hook Job (WP-CLI) that installs WordPress and WooCommerce, sets INR and cash on delivery, adds sample products and registers the REST API key |
| woo-mcp | Python MCP server with 5 tools. It calls the WooCommerce REST API at `wordpress:80` with a key pair from a Secret |
| notes-mcp, utility-mcp | Small servers so the gateway has three upstreams |
| Gateway | Keys, roles, registry, `/mcp` endpoint, routing, audit log, chat agent, dashboard API. SQLite on a PVC |
| Dashboard | React (Vite) served by nginx. The Ingress sends `/` to it and `/api` to the gateway, so the browser sees one origin and needs no CORS |

## Tool aggregation, routing and failure handling
- **Naming:** tools are exposed as `<server>__<tool>`. Server names are lowercase letters and digits, so the first `__` splits cleanly and two servers can never clash.
- **Listing:** the gateway asks every enabled server in parallel with a 5 s timeout. A dead server is reported as Unreachable and the rest still list.
- **Calling:** it splits the name, checks the server is enabled, strips the prefix and forwards the call with a 15 s timeout. Failures return a clear message, never a hang.
- **Audit:** one row per call (who, server, tool, duration, outcome). Arguments are not stored, because they can contain customer data.
- **Chat agent:** a loop of at most 6 rounds. The model asks for a tool, the gateway runs it **as the signed-in user** through the same code as `/mcp`, and the result goes back to the model. Results are cut at 6,000 characters. The LLM key stays server-side.

## Choices and tradeoffs
- **SQLite instead of Postgres:** one file, no extra pod, light on an 8 GB laptop. Cost: one gateway replica (a ReadWriteOnce disk, so the Deployment uses `Recreate`). Production would use Postgres to scale out.
- **Hand-written `/mcp`:** the gateway owns key checks, routing and the audit log, and stays stateless. Cost: no streaming or server-initiated messages, and it implements only the methods we need (`initialize`, `ping`, `tools/list`, `tools/call`).
- **Separate databases:** the store (MariaDB, required by WordPress) and the gateway (SQLite) have different lifecycles and trust levels.
- **Hashing:** API keys use SHA-256 (long random values). Passwords use salted scrypt (human-chosen). Upstream credentials are stored **in clear text**, because the gateway must send them.
- **No per-tool permissions:** members are trusted staff and may use every enabled tool. Roles split management (admin) from use (member).
- **WooCommerce auth:** over plain HTTP WooCommerce rejects a simple key pair, so woo-mcp sends `X-Forwarded-Proto: https` on its in-cluster calls. In production TLS ends at the Ingress.

## What changes for production
DNS and domains in the three `values-prod.yaml` files, `ingressClassName: traefik`, `storageClass: local-path` (or the provider's class), TLS through cert-manager, images from a registry, Secrets from a secret manager, Postgres instead of SQLite, and encrypting the upstream credentials. Details are in the README.
