#!/usr/bin/env bash
#
# pr-context.sh - Gather everything needed to understand a PR's intent
#
# Usage: pr-context.sh [PR_URL | PR_NUMBER]
#
# Prints the PR description, linked issues, commit messages, changed-file stats,
# and any existing review comments. Read this BEFORE reading the diff so the
# review judges the change against what it claims to do.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-pr.sh"

IFS=$'\t' read -r PR_NUMBER PR_REPO < <(resolve_pr "${1:-}")

echo "${PR_REPO} PR #${PR_NUMBER} - Review Context"
echo "=========================================="

echo ""
echo "## Intent (description, author, base)"
gh pr view "$PR_NUMBER" --repo "$PR_REPO" --json title,author,baseRefName,headRefName,state,isDraft,body --jq '
    "Title:  \(.title)\n" +
    "Author: \(.author.login)\n" +
    "Branch: \(.headRefName) -> \(.baseRefName)\n" +
    "State:  \(.state)\(if .isDraft then " (draft)" else "" end)\n\n" +
    "--- Description ---\n" +
    (if (.body | length) == 0 then "(no description provided)" else .body end)
'

echo ""
echo "## Linked Issues"
gh pr view "$PR_NUMBER" --repo "$PR_REPO" --json closingIssuesReferences --jq '
    if (.closingIssuesReferences | length) == 0 then
        "(none linked)"
    else
        .closingIssuesReferences[] | "#\(.number): \(.title)"
    end
'

echo ""
echo "## Commits"
gh pr view "$PR_NUMBER" --repo "$PR_REPO" --json commits --jq '
    .commits[] | "\(.oid[0:8])  \(.messageHeadline)"
'

echo ""
echo "## Changed Files"
gh pr view "$PR_NUMBER" --repo "$PR_REPO" --json files --jq '
    .files[] | "\(.path)  (+\(.additions)/-\(.deletions))"
'

echo ""
echo "## Existing Review Comments (avoid duplicating these)"
gh api "repos/${PR_REPO}/pulls/${PR_NUMBER}/comments" --paginate --jq '
    .[] | "[\(.user.login)] \(.path):\(.line // .original_line // "?")\n\(.body)\n"
' 2>/dev/null || true

echo ""
echo "=========================================="
echo "Next: read the diff with 'gh pr diff ${PR_NUMBER} --repo ${PR_REPO}', then read"
echo "the full versions of the changed files for surrounding context."
