#!/usr/bin/env bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
set -e

cd "$(dirname "$0")"

export OPENCLAW_LOCAL_ANTHROPIC_KEY="sk-84878ee8801347219b6ffa6c6db8338b"
export OPENCLAW_LOCAL_GEMINI_KEY="sk-84878ee8801347219b6ffa6c6db8338b"
export OPENCLAW_GEMINI_API_ENDPOINT="http://127.0.0.1:8045"
export GEMINI_API_ENDPOINT="http://127.0.0.1:8045"
export OPENCLAW_GEMINI_IMAGE_MODEL="gemini-3-pro-image"
export GEMINI_IMAGE_MODEL="gemini-3-pro-image"
export OPENCLAW_PROFILE=dev
export OPENCLAW_STATE_DIR=/Users/kiyoliang/.openclaw-dev
export OPENCLAW_CONFIG_PATH=/Users/kiyoliang/.openclaw-dev/openclaw.json
export OPENCLAW_GATEWAY_PORT=19001
export OPENCLAW_GATEWAY_TOKEN=dev
# export OPENCLAW_SKIP_CHANNELS=1
# export CLAWDBOT_SKIP_CHANNELS=1

python3 - <<'PY'
import json
from pathlib import Path

prod_path = Path("/Users/kiyoliang/.openclaw/openclaw.json")
dev_path = Path("/Users/kiyoliang/.openclaw-dev/openclaw.json")

prod = json.loads(prod_path.read_text())
dev = json.loads(dev_path.read_text())

prod_defaults = prod.get("agents", {}).get("defaults", {})
keys = ("model", "imageModel", "models")

dev.setdefault("agents", {}).setdefault("defaults", {})
for key in keys:
    if key in prod_defaults:
        dev["agents"]["defaults"][key] = prod_defaults[key]

dev_path.write_text(json.dumps(dev, indent=2, ensure_ascii=False) + "\n")
PY

kill -9 $(lsof -tiTCP:19001 -sTCP:LISTEN 2>/dev/null) 2>/dev/null || true

nohup node --import /Users/kiyoliang/.openclaw-dev/llm-proxy-preload.mjs --import tsx src/entry.ts --dev gateway \
  > /tmp/openclaw-dev-gateway.log 2>&1 &

echo "Dev gateway: http://127.0.0.1:19001/?token=dev"
