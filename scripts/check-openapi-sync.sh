#! /usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > "$ROOT_DIR/frontend/openapi.json"

cd "$ROOT_DIR/frontend"
bun run generate-client

cd "$ROOT_DIR"
git diff --exit-code -- frontend/openapi.json frontend/src/client
