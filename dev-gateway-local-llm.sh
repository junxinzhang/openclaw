#!/usr/bin/env bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
set -e

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  echo "Please run this script as your login user (not root) so SSH auth/known_hosts match production." >&2
  exit 1
fi

cd "$(dirname "$0")"

export USER_HOME="${HOME:-/Users/kiyoliang}"

export OPENCLAW_LOCAL_ANTHROPIC_KEY="sk-84878ee8801347219b6ffa6c6db8338b"
export OPENCLAW_LOCAL_GEMINI_KEY="sk-84878ee8801347219b6ffa6c6db8338b"
export OPENCLAW_GEMINI_API_ENDPOINT="http://127.0.0.1:8045"
export GEMINI_API_ENDPOINT="http://127.0.0.1:8045"
export OPENCLAW_GEMINI_IMAGE_MODEL="gemini-3-pro-image"
export GEMINI_IMAGE_MODEL="gemini-3-pro-image"
export OPENCLAW_PROFILE=dev
export OPENCLAW_STATE_DIR="${USER_HOME}/.openclaw-dev"
export OPENCLAW_CONFIG_PATH="${OPENCLAW_STATE_DIR}/openclaw.json"
export OPENCLAW_GATEWAY_PORT=19001
export OPENCLAW_GATEWAY_TOKEN=dev
# Inherit SSH agent for git operations (match login shell / production gateway)
if [ -z "${SSH_AUTH_SOCK:-}" ] || [ ! -S "${SSH_AUTH_SOCK}" ]; then
  if command -v launchctl >/dev/null 2>&1; then
    LAUNCHD_SOCK="$(launchctl getenv SSH_AUTH_SOCK 2>/dev/null || true)"
    if [ -n "${LAUNCHD_SOCK}" ] && [ -S "${LAUNCHD_SOCK}" ]; then
      export SSH_AUTH_SOCK="${LAUNCHD_SOCK}"
    fi
  fi
fi
if [ -n "${SSH_AUTH_SOCK:-}" ] && [ ! -S "${SSH_AUTH_SOCK}" ]; then
  echo "Warning: SSH_AUTH_SOCK is set but not a valid socket; git over SSH may fail." >&2
fi
# export OPENCLAW_SKIP_CHANNELS=1
# export CLAWDBOT_SKIP_CHANNELS=1

python3 - <<'PY'
import json
from pathlib import Path

home = Path(__import__("os").environ.get("USER_HOME", "/Users/kiyoliang"))
prod_path = home / ".openclaw" / "openclaw.json"
dev_path = home / ".openclaw-dev" / "openclaw.json"

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

# Kill any process listening on 19001 (Server)
# We purposely ignore ESTABLISHED connections (like Browser clients) to avoid killing them.
GATEWAY_PID=$(lsof -tiTCP:19001 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$GATEWAY_PID" ]; then
  echo "Stopping existing gateway (PID: $GATEWAY_PID)..."
  kill -9 "$GATEWAY_PID"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Use NODE_OPTIONS to load preload modules
export NODE_OPTIONS="--import $SCRIPT_DIR/node_modules/tsx/dist/loader.mjs"
## --import /Users/kiyoliang/.openclaw-dev/llm-proxy-preload.mjs"

# Use pnpm openclaw directly
nohup /opt/homebrew/bin/pnpm openclaw --dev gateway > /tmp/openclaw-dev-gateway.log 2>&1 &

echo "Dev gateway: http://127.0.0.1:19001/?token=dev"
