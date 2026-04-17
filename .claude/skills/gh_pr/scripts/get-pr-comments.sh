#!/usr/bin/env bash
#
# get-pr-comments.sh - Fetch unresolved PR review comments
#
# Usage: get-pr-comments.sh [PR_NUMBER]
#
# If PR_NUMBER is not provided, uses the PR associated with the current branch.
# Filters out comment threads that have already been addressed by Claude Code
# (identified by replies containing "[Claude Code]" prefix).

set -euo pipefail

PR_NUMBER="${1:-}"

# Get PR number from current branch if not provided
if [[ -z "$PR_NUMBER" ]]; then
    PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")
    if [[ -z "$PR_NUMBER" ]]; then
        echo "Error: No PR found for current branch and no PR number provided." >&2
        exit 1
    fi
fi

echo "Fetching comments for PR #${PR_NUMBER}..."
echo "=========================================="

# Fetch review comments (inline code comments)
echo ""
echo "## Review Comments (Inline)"
echo ""

gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/comments" --jq '
    .[] |
    "### Comment ID: \(.id)\n" +
    "**File:** \(.path):\(.line // .original_line // "N/A")\n" +
    "**Author:** \(.user.login)\n" +
    "**Created:** \(.created_at)\n" +
    "**In Reply To:** \(.in_reply_to_id // "N/A")\n\n" +
    "```\n\(.body)\n```\n" +
    "---"
' 2>/dev/null || echo "No review comments found."

# Fetch issue comments (general PR comments)
echo ""
echo "## General PR Comments"
echo ""

gh api "repos/{owner}/{repo}/issues/${PR_NUMBER}/comments" --jq '
    .[] |
    select(.body | test("^\\[Claude Code\\]") | not) |
    "### Comment ID: \(.id)\n" +
    "**Author:** \(.user.login)\n" +
    "**Created:** \(.created_at)\n\n" +
    "```\n\(.body)\n```\n" +
    "---"
' 2>/dev/null || echo "No general comments found."

echo ""
echo "=========================================="
echo "To reply to a comment, use:"
echo "  .claude/skills/gh_pr/scripts/reply-to-comment.sh <COMMENT_ID> \"<response>\""
