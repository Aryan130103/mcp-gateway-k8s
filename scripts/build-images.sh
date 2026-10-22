#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER="${CLUSTER:-urumi}"
have_k3d_cluster() { command -v k3d >/dev/null 2>&1 && k3d cluster list --no-headers 2>/dev/null | awk '{print $1}' | grep -qx "$CLUSTER"; }
build() {
  docker build -q -t "$2" "$1" >/dev/null
  echo "built $2"
  if have_k3d_cluster; then k3d image import "$2" -c "$CLUSTER" >/dev/null; echo "imported $2 into k3d cluster $CLUSTER"; fi
}
tag() { grep -E '^image:' "$1" | head -1 | awk '{print $2}'; }
extra_tag() { grep -A1 "name: $1" charts/extra-mcp/values.yaml | grep image | awk '{print $2}'; }
build mcp-servers/woo "$(tag charts/woo-mcp/values.yaml)"
build mcp-servers/notes "$(extra_tag notes-mcp)"
build mcp-servers/utility "$(extra_tag utility-mcp)"
build gateway "$(tag charts/gateway/values.yaml)"
build dashboard "$(tag charts/dashboard/values.yaml)"
