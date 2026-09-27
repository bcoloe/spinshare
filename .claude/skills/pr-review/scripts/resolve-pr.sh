#!/usr/bin/env bash
#
# resolve-pr.sh - Resolve a PR reference into a number and a repo
#
# Usage: resolve-pr.sh [PR_URL | PR_NUMBER]
#
# Accepts a full GitHub PR URL, a bare PR number, a "#123" form, or nothing at
# all (in which case the PR for the current branch is used). Prints:
#
#   <PR_NUMBER><TAB><OWNER/REPO>
#
# Other scripts source this so a URL for a *different* repo is honored: the gh
# "{owner}/{repo}" placeholders always expand to the current directory's repo,
# which would silently review the wrong PR.

set -euo pipefail
shopt -s extglob

resolve_pr() {
    local ref="${1:-}"
    local number="" repo=""

    # Strip a query string, and a #discussion anchor on URLs only -- a bare
    # "#123" is a valid PR reference and must survive.
    ref="${ref%%\?*}"
    [[ "$ref" == http?(s)://* ]] && ref="${ref%%#*}"

    if [[ "$ref" =~ ^https?://[^/]+/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
        repo="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
        number="${BASH_REMATCH[3]}"
    elif [[ "$ref" =~ ^#?([0-9]+)$ ]]; then
        number="${BASH_REMATCH[1]}"
    elif [[ -n "$ref" ]]; then
        echo "Error: '${ref}' is not a PR URL or number." >&2
        echo "Expected https://github.com/OWNER/REPO/pull/123, or 123, or nothing." >&2
        return 1
    fi

    if [[ -z "$repo" ]]; then
        repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")
        if [[ -z "$repo" ]]; then
            echo "Error: not inside a GitHub repo and no PR URL given." >&2
            return 1
        fi
    fi

    if [[ -z "$number" ]]; then
        number=$(gh pr view --repo "$repo" --json number --jq '.number' 2>/dev/null || echo "")
        if [[ -z "$number" ]]; then
            echo "Error: no PR found for the current branch; pass a PR URL or number." >&2
            return 1
        fi
    fi

    printf '%s\t%s\n' "$number" "$repo"
}

# Allow both `source resolve-pr.sh` and direct invocation.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    resolve_pr "${1:-}"
fi
