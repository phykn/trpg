#!/usr/bin/env bash
# Relational SSOT guard — fails when `game/runtime/`, `llm/context/`, or `wire/`
# code reads an entity's relation field as a *list* (iterating across
# many ids) instead of asking the graph. Full rule + the value-vs-relation
# distinction is in server/AGENTS.md.
#
# Run from repo root: bash server/scripts/check_relational_ssot.sh
# Exits non-zero with a one-line-per-violation summary if anything is found.
#
# Scope of forbidden patterns:
# - List-shaped relation fields (inventory, racial_skills,
#   learned_skills, connections, items, quests, companions,
#   triggers[]) — iterating these is the same shape as a graph scan.
# - state.characters.items() / .values() — iterating *all* characters
#   to filter by relation is the textbook fullscan.
#
# Scalar pointers (location, race, giver) are NOT in the list:
# reading "what's this one entity's own location" is the entity's own
# value-attribute and typically used as the start key for a graph query.
# Same for `equipment.<slot>` — single slot pickup, not iteration.
#
# To whitelist a justified single line (write path, attribute-only sweep
# like buff ticking), add `# ssot-allow:` on the same line as a brief
# reason. The grep skips those.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SEARCH_DIRS=(
  "$ROOT/server/src/game/runtime"
  "$ROOT/server/src/llm/context"
  "$ROOT/server/src/wire"
)

FORBIDDEN_PATTERNS=(
  '\.inventory\b'
  '\.racial_skills\b'
  '\.learned_skills\b'
  '\.connections\b'
  '\.items\b'
  '\.quests\b'
  '\.companions\b'
  '\.triggers\['
  'state\.characters\.items\(\)'
  'state\.characters\.values\(\)'
)

violations=0
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  for dir in "${SEARCH_DIRS[@]}"; do
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      file="${line%%:*}"
      rest="${line#*:}"
      lineno="${rest%%:*}"
      content="${rest#*:}"
      if echo "$content" | grep -qE '#\s*ssot-allow'; then
        continue
      fi
      echo "  ${file#$ROOT/}:${lineno}  $(echo "$content" | sed 's/^[[:space:]]*//' | cut -c1-100)"
      violations=$((violations + 1))
    done < <(grep -rEn "$pattern" --include='*.py' "$dir" 2>/dev/null || true)
  done
done

if [[ $violations -gt 0 ]]; then
  echo
  echo "❌ relational SSOT guard: $violations direct relation-iteration reads found in game.runtime/llm.context/wire."
  echo "   Use ontology/graph queries instead, or mark the line with '# ssot-allow: <reason>' if it's a justified exception (write path, attribute-only sweep, etc)."
  echo "   See server/AGENTS.md for the full rule."
  exit 1
fi

echo "✅ relational SSOT guard: clean."
