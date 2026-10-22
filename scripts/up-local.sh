#!/usr/bin/env bash
# One command on a laptop: cluster + images + everything.  Usage: [LLM_API_KEY=...] ./scripts/up-local.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER="${CLUSTER:-urumi}"
if ! k3d cluster list --no-headers 2>/dev/null | awk '{print $1}' | grep -qx "$CLUSTER"; then
  k3d cluster create "$CLUSTER" -p "80:80@loadbalancer"
fi
./scripts/build-images.sh
./scripts/install.sh
