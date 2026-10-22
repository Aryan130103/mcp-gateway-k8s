#!/usr/bin/env bash
# Usage: [ENVIRONMENT=local|prod] [NAMESPACE=mcp-gateway] [ADMIN_NAME=admin] [LLM_API_KEY=...] ./scripts/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ENVIRONMENT="${ENVIRONMENT:-local}"
NS="${NAMESPACE:-mcp-gateway}"
ADMIN_NAME="${ADMIN_NAME:-admin}"

./scripts/gen-secrets.sh
kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

if [ -n "${LLM_API_KEY:-}" ]; then
  kubectl -n "$NS" create secret generic llm-secret --from-literal=api-key="$LLM_API_KEY" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  echo "llm-secret set: chat enabled"
else
  echo "LLM_API_KEY not set: chat will say it is not configured; everything else works"
fi

install() {
  local release="$1" chart="$2"; shift 2
  echo "==> installing $release"
  helm upgrade --install "$release" "charts/$chart" -n "$NS" \
    -f "charts/$chart/values-$ENVIRONMENT.yaml" "$@" --wait --timeout 10m
}
install store store -f charts/store/secrets.local.yaml
install woo-mcp woo-mcp
install extra-mcp extra-mcp
install gateway gateway
install dashboard dashboard

gw() { kubectl -n "$NS" exec deploy/gateway -- "$@"; }
echo "==> first admin and default servers"
EXISTS=$(gw python -c "import sqlite3;c=sqlite3.connect('/data/gateway.db');print(c.execute('select count(*) from users where name=?',('$ADMIN_NAME',)).fetchone()[0])")
PASSWORD=""
if [ "$EXISTS" = "0" ]; then
  gw python manage.py create-admin "$ADMIN_NAME" >/dev/null
  PASSWORD=$(gw python manage.py set-password "$ADMIN_NAME" 2>/dev/null | tail -1)
fi
gw python -c "
import sqlite3
c = sqlite3.connect('/data/gateway.db')
for n, u in [('woo','http://woo-mcp:8000/mcp'),('notes','http://notes-mcp:8000/mcp'),('utility','http://utility-mcp:8000/mcp')]:
    c.execute('INSERT OR IGNORE INTO mcp_servers (name, url, enabled) VALUES (?, ?, 1)', (n, u))
c.commit()
print('servers registered')
"

echo
echo "Ready. Namespace: $NS ($ENVIRONMENT)"
for f in store dashboard gateway; do :; done
kubectl -n "$NS" get ingress -o custom-columns=HOST:.spec.rules[0].host --no-headers | sed 's#^#  http://#'
if [ -n "$PASSWORD" ]; then
  echo "Admin login: $ADMIN_NAME / $PASSWORD   (shown once, save it)"
else
  echo "Admin '$ADMIN_NAME' already exists. Reset: kubectl -n $NS exec deploy/gateway -- python manage.py set-password $ADMIN_NAME"
fi
echo "Store admin password: kubectl -n $NS get secret wp-admin-secret -o jsonpath='{.data.admin-password}' | base64 -d; echo"
