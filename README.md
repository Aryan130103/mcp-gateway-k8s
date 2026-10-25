# MCP Gateway on Kubernetes

A gateway that puts many MCP servers behind one endpoint, with API keys, roles, an audit log, a React dashboard and a chat agent. The first data source is a WooCommerce store. Everything runs on Kubernetes (k3d locally, k3s in production).

**Components**

- WooCommerce store (WordPress + MariaDB)
- WooCommerce MCP server
- Two small extra MCP servers (notes, utility)
- Gateway (FastAPI + SQLite)
- React dashboard
- Chat agent (inside the gateway)

**Docs**

- [System design and tradeoffs](docs/design.md)
- [Threat model](docs/threat-model.md)

## Local setup

Needs: Docker, [k3d](https://k3d.io), kubectl, helm, openssl, about 8 GB RAM, and port 80 free. `*.localtest.me` resolves to 127.0.0.1 through public DNS, so no hosts-file edits are needed (internet required).

```bash
git clone https://github.com/Aryan130103/mcp-gateway-k8s.git
cd mcp-gateway-k8s
```

Then run the installer. The LLM key is optional; without it only the chat is disabled.

```bash
LLM_API_KEY=your-llm-key ./scripts/up-local.sh
```

This creates the k3d cluster, generates secrets (git-ignored), builds and imports the images, installs the six charts into the `mcp-gateway` namespace, creates the first admin and registers the three servers. It takes roughly 10-15 minutes and prints the URLs and the **admin password (shown once)**.

| What | URL |
|---|---|
| Store | http://shop.localtest.me/shop/ |
| Dashboard | http://dashboard.localtest.me |
| Gateway MCP endpoint | http://gateway.localtest.me/mcp |

### Logins

**Dashboard (gateway admin):** user `admin`, with the password printed once at the end of the install. If you lose it, set a new one. The last line printed is the new password.

```bash
kubectl -n mcp-gateway exec deploy/gateway -- python manage.py set-password admin
```

**Store admin (WordPress):** user `admin` at http://shop.localtest.me/wp-admin. Print its password:

```bash
kubectl -n mcp-gateway get secret wp-admin-secret -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

The chat works with any OpenAI-compatible provider. Set `llm.baseUrl` and `llm.model` in the `llm` section of `charts/gateway/values.yaml`; the key goes in the `llm-secret` Secret. Tested with Gemini.

## Place an order

Open the store, add a product to the cart, check out with made-up details and choose **Cash on delivery**. Then ask the chat "What orders came in today?" or open the audit log.

## Connect an external MCP client

Any MCP client that supports Streamable HTTP works. These steps use MCP Inspector.

**1. Get an API key.** Members generate their own in the dashboard (API keys tab, shown once). To get an admin key from the terminal, run this. It prints a key starting with `gw_` once:

```bash
kubectl -n mcp-gateway exec deploy/gateway -- python -c "from auth import create_key_for; print(create_key_for(1, 'inspector'))"
```

**2. Start Inspector.**

```bash
npx @modelcontextprotocol/inspector
```

It prints a link such as `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...`. Open that exact link in your browser.

**3. Add the gateway as a server.** Transport: Streamable HTTP. Then set the URL and the header (the header goes in the server's settings):

```
URL:     http://gateway.localtest.me/mcp
Header:  Authorization: Bearer <your key>
```

**4. Try it.** The Tools tab lists the tools of every enabled server, named `<server>__<tool>`. Disable a server in the dashboard and its tools disappear. Revoke the key and the next call is rejected.

**Check without Inspector:**

```bash
curl -s -X POST http://gateway.localtest.me/mcp \
  -H "Authorization: Bearer <your key>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Claude Code can connect the same way (not tested here, it needs a paid plan):

```bash
claude mcp add --transport http gateway http://gateway.localtest.me/mcp --header "Authorization: Bearer <your key>"
```

## Use the chat agent

Dashboard → **Chat**. Ask for example "List the products", or "Create a product called Chai Cup at 199 rupees and save a note about it". Each answer lists the tools it used. The agent acts as the signed-in user, so permissions and the audit log apply.

## VPS / production-like setup (documented, not deployed in this submission)

1. Install k3s on a server (it ships Traefik and `local-path` storage, which `values-prod.yaml` expects).
2. Create DNS A records for shop., gateway. and dashboard. pointing at the server.
3. Replace `example.com` in `charts/store`, `charts/gateway` and `charts/dashboard` `values-prod.yaml` **before the first install**.
4. Build the five images, push them to a registry and set the `image:` values in the prod files (`build-images.sh` imports into k3d only).
5. `ENVIRONMENT=prod LLM_API_KEY=... ./scripts/install.sh`
6. TLS is **not configured**. Add cert-manager and an Ingress TLS section before exposing it, because keys and passwords travel in clear text over plain HTTP.

| Setting | Local | Production |
|---|---|---|
| Hostnames | `*.localtest.me` | your domains |
| Disks | 1-2 Gi, default class | 5-10 Gi, `local-path` |
| Ingress class | default | `traefik` |
| Memory limits | small | larger |
| Secrets | generated by script | generated or supplied; use an external secret manager for real deployments |

## Upgrade and rollback

```bash
helm upgrade gateway charts/gateway -n mcp-gateway -f charts/gateway/values-local.yaml --set image=gateway:<new-tag>
helm history gateway -n mcp-gateway
helm rollback gateway <revision> -n mcp-gateway
```
Database changes are additive (`ALTER TABLE ... ADD COLUMN`), so rolling the gateway back leaves the data usable. The store chart re-runs its setup job on every upgrade and is safe to repeat. Data lives on PVCs, so pod restarts and upgrades keep it.

## Repo layout

```
charts/            Helm charts, each with values-local.yaml and values-prod.yaml
  store/             WordPress, WooCommerce, MariaDB, setup job
  woo-mcp/           WooCommerce MCP server
  extra-mcp/         notes and utility MCP servers
  gateway/           gateway backend
  dashboard/         React dashboard
  network-policies/  default-deny rules and allow rules
gateway/           gateway backend, MCP endpoint, chat agent (Python)
dashboard/         React app (Vite)
mcp-servers/       woo/, notes/, utility/
scripts/           up-local.sh, install.sh, build-images.sh, gen-secrets.sh
docs/              design.md, threat-model.md
```

## Stand-out items attempted

**Security hardening:** default-deny ingress NetworkPolicies (`charts/network-policies`), non-root containers with dropped capabilities for our own services, hashed API keys (SHA-256) and hashed passwords (scrypt). Not attempted: the other extras.
