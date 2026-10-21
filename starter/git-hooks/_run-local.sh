# Sourced by the global hooks in this folder, never run directly.
#
# Once `core.hooksPath` points here, git stops running each repo's own
# .git/hooks/ (where many tools install their hooks). Every global hook therefore also runs the repo's
# hook of the same name, so the global policy and the repo's hooks both apply.
#
# Repos that set their own local core.hooksPath (husky, .githooks) override this
# folder entirely; git runs neither these global hooks nor .git/hooks there.

run_local_hook() {
  local name="$1"
  shift
  local dir
  dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 0
  local hook="$dir/hooks/$name"
  [ -x "$hook" ] || return 0
  "$hook" "$@"
}
