#!/usr/bin/env bash
# Run ON the Google Cloud VM after every start:  bash tools/gcp_https.sh
# Points Caddy (HTTPS) at the VM's current public IP using a free sslip.io name.
set -euo pipefail

IP=$(curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip")
if [ -z "$IP" ]; then
  echo "Could not read the VM's external IP" >&2
  exit 1
fi
HOST="$(echo "$IP" | tr . -).sslip.io"

sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$HOST {
    reverse_proxy 127.0.0.1:8000
}
EOF
sudo systemctl enable --now caddy >/dev/null 2>&1 || true
sudo systemctl reload caddy

echo
echo "Your HTTPS address (give this to the camera client and open it in a browser):"
echo "  https://$HOST"
echo "The certificate takes ~30 seconds the first time."
