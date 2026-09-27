#!/usr/bin/env bash
#
# diff-lines.sh - List every line of a PR diff that an inline comment can anchor to
#
# Usage: diff-lines.sh [PR_URL | PR_NUMBER] [--with-content]
#
# Emits one "<path>:<line>" per commentable position on the RIGHT side of the
# diff (added and context lines). With --with-content, appends a TAB and the
# text of that line, which post-review.sh uses to show anchors in a preview.
#
# GitHub rejects a review whose comment points at a line outside the diff hunks,
# so post-review.sh validates every anchor against this list.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-pr.sh"

PR_REF=""
WITH_CONTENT=0
for arg in "$@"; do
    case "$arg" in
        --with-content) WITH_CONTENT=1 ;;
        *) [[ -z "$PR_REF" ]] && PR_REF="$arg" ;;
    esac
done

IFS=$'\t' read -r PR_NUMBER PR_REPO < <(resolve_pr "$PR_REF")

gh pr diff "$PR_NUMBER" --repo "$PR_REPO" | awk -v with_content="$WITH_CONTENT" '
    /^\+\+\+ / { path = substr($0, 5); sub(/^b\//, "", path); next }
    /^@@ /     { match($0, /\+[0-9]+/); newline = substr($0, RSTART + 1, RLENGTH - 1) + 0; next }
    path == "" { next }
    /^\\/      { next }
    /^-/       { next }
    /^[+ ]/ {
        if (with_content) print path ":" newline "\t" substr($0, 2)
        else              print path ":" newline
        newline++
    }
'
