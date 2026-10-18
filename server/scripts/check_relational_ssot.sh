#!/usr/bin/env bash
# Keep edge traversal in src/world/graph.py and src/world/query.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
violations=$(grep -rnE '\.edges\b|\.nodes\.(values|items)\(' "$ROOT/server/src" \
  | grep -v -e "/src/world/graph.py:" -e "/src/world/query.py:" || true)
if [[ -n "$violations" ]]; then
  echo "$violations"
  echo "Use graph query helpers for relations."
  exit 1
fi
echo "Graph relation checks passed."
