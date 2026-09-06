#!/usr/bin/env bash
set -euo pipefail

echo "Starting HTTPS tunnel to http://localhost:8000"
echo "Copy the generated trycloudflare.com URL into Vercel as:"
echo "NEXT_PUBLIC_API_URL=<tunnel-url>/api/v1"

if command -v cloudflared >/dev/null 2>&1; then
  exec cloudflared tunnel --url http://localhost:8000
fi

if command -v docker >/dev/null 2>&1; then
  exec docker run --rm --network host \
    cloudflare/cloudflared:latest \
    tunnel --no-autoupdate --url http://localhost:8000
fi

echo "Neither cloudflared nor Docker is installed."
exit 1
