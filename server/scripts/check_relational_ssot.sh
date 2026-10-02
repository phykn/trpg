#!/usr/bin/env bash
# Keep relation traversal in game/graph/query.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FILES=(src/api.py src/service.py src/view.py src/game/engine.py src/game/combat.py src/game/move.py)
violations=0
for name in "${FILES[@]}"; do
  file="$ROOT/server/$name"
  [[ -f "$file" ]] || { echo "Missing source: $name"; exit 1; }
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    echo "$name:$line"
    violations=$((violations + 1))
  done < <(grep -En '\.edges\b|\.nodes\.(values|items)\(' "$file" || true)
done
[[ "$violations" -eq 0 ]] || { echo "Use graph query helpers for relations."; exit 1; }
echo "Graph relation checks passed."
