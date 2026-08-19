#!/usr/bin/env bash
# Deterministic structure checks for the dual-loop workflow's generated docs.
# Replaces "read the file back and eyeball it" with a grep/awk check —
# see cost-aware-orchestration / the 2026-08-19 tokenomics review for why.
#
# Usage:
#   check-doc-structure.sh prd <file>
#   check-doc-structure.sh architecture <file>
#   check-doc-structure.sh ticket <file>
#   check-doc-structure.sh ticket-conflicts <tickets-dir>
#   check-doc-structure.sh plan <file>
#
# Exit 0 = pass. Exit 1 = fail, with the specific reason on stdout.
# "ticket-conflicts" only ever warns (exit 0) — overlap across tickets isn't
# necessarily a real conflict, that judgment call stays with the reviewer.

set -u
fail=0

# section_nonempty <file> <heading-regex> <human-label>
# Finds a markdown heading matching the regex, confirms there's at least one
# non-blank, non-heading line before the next heading (or EOF).
section_nonempty() {
  local file="$1" pattern="$2" label="$3"
  awk -v pat="$pattern" -v label="$label" '
    BEGIN { found=0; has_content=0; in_section=0 }
    /^#+[ \t]/ {
      if (in_section) { in_section=0 }
      if ($0 ~ pat) { found=1; in_section=1; next }
    }
    in_section && $0 !~ /^[ \t]*$/ { has_content=1 }
    END {
      if (!found) { print "MISSING: " label; exit 1 }
      if (!has_content) { print "EMPTY: " label; exit 1 }
    }
  ' "$file"
}

check_prd() {
  local file="$1"
  section_nonempty "$file" "[Ss]cope" "Scope" || fail=1
  section_nonempty "$file" "[Nn]on-[Gg]oals" "Non-Goals" || fail=1
  section_nonempty "$file" "[Ss]uccess [Mm]etrics" "Success Metrics" || fail=1
}

check_architecture() {
  local file="$1"
  section_nonempty "$file" "[Cc]omponents" "Components" || fail=1
  section_nonempty "$file" "[Ii]nterfaces" "Interfaces" || fail=1
  section_nonempty "$file" "[Dd]ata [Ff]lows?" "Data Flow(s)" || fail=1
  section_nonempty "$file" "[Nn]on-[Gg]oals" "Non-Goals" || fail=1
  echo "NOTE: interface-to-component mapping is a semantic check — still needs a read, this script only confirms sections exist and aren't empty."
}

check_ticket() {
  local file="$1"
  section_nonempty "$file" "[Ss]cope" "Scope" || fail=1
  section_nonempty "$file" "[Ff]iles" "Files (likely touched)" || fail=1
  section_nonempty "$file" "[Dd]efinition of [Dd]one" "Definition of Done" || fail=1
}

check_ticket_conflicts() {
  local dir="$1"
  local tmp
  tmp=$(mktemp)
  for f in "$dir"/*.md; do
    [ -f "$f" ] || continue
    awk -v ticket="$(basename "$f")" '
      /^#+[ \t]*[Ff]iles/ { in_section=1; next }
      /^#+[ \t]/ { in_section=0 }
      in_section && /^[ \t]*[-*][ \t]/ { sub(/^[ \t]*[-*][ \t]+/, ""); print $0 "\t" ticket }
    ' "$f" >> "$tmp"
  done
  local dupes
  dupes=$(cut -f1 "$tmp" | sort | uniq -d)
  if [ -n "$dupes" ]; then
    echo "OVERLAP (review, not necessarily a real conflict):"
    while IFS= read -r path; do
      grep -F "$path" "$tmp" | awk -F'\t' -v p="$path" '{print "  " p " <- " $2}'
    done <<< "$dupes"
  else
    echo "No file overlap across tickets in $dir"
  fi
  rm -f "$tmp"
}

check_plan() {
  local file="$1"
  local bad
  bad=$(grep -nE '^[ \t]*[0-9]+\.' "$file" | grep -viE 'verify:' || true)
  if [ -n "$bad" ]; then
    echo "STEP MISSING verify: clause —"
    echo "$bad"
    fail=1
  fi
}

main() {
  local mode="${1:-}" target="${2:-}"
  if [ -z "$mode" ] || [ -z "$target" ]; then
    echo "usage: check-doc-structure.sh <prd|architecture|ticket|ticket-conflicts|plan> <file-or-dir>" >&2
    exit 2
  fi
  case "$mode" in
    prd) check_prd "$target" ;;
    architecture) check_architecture "$target" ;;
    ticket) check_ticket "$target" ;;
    ticket-conflicts) check_ticket_conflicts "$target" ;;
    plan) check_plan "$target" ;;
    *) echo "unknown mode: $mode" >&2; exit 2 ;;
  esac
  if [ "$fail" -eq 0 ]; then
    echo "PASS"
  fi
  exit "$fail"
}

main "$@"
