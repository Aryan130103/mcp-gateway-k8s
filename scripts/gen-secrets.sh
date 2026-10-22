#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
f=charts/store/secrets.local.yaml
if [ -f "$f" ]; then echo "secrets exist, left unchanged: $f"; exit 0; fi
cat > "$f" <<YAML
secrets:
  mariadbRootPassword: $(openssl rand -hex 12)
  mariadbPassword: $(openssl rand -hex 12)
  wpAdminPassword: $(openssl rand -hex 8)
  wooConsumerKey: ck_$(openssl rand -hex 20)
  wooConsumerSecret: cs_$(openssl rand -hex 20)
YAML
chmod 600 "$f"
echo "created $f (git-ignored)"
