#!/usr/bin/env bash
#
# reply-to-comment.sh - Reply to a PR comment thread
#
# Usage: reply-to-comment.sh <COMMENT_ID> "<response>" [--type=review|issue]
#
# COMMENT_ID: The ID of the comment to reply to
# response: The reply message (will be prefixed with "[Claude Code]")
# --type: Specify comment type (review for inline, issue for general). Default: review
#
# All replies are automatically prefixed with "[Claude Code]" to identify
# AI-generated responses for tracking purposes.

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: reply-to-comment.sh <COMMENT_ID> \"<response>\" [--type=review|issue]" >&2
    exit 1
fi

COMMENT_ID="$1"
RESPONSE="$2"
COMMENT_TYPE="review"

# Parse optional --type flag
for arg in "${@:3}"; do
    case "$arg" in
        --type=*)
            COMMENT_TYPE="${arg#*=}"
            ;;
    esac
done

# Prefix with Claude Code identifier
PREFIXED_RESPONSE="[Claude Code] ${RESPONSE}"

# Get current PR number
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")
if [[ -z "$PR_NUMBER" ]]; then
    echo "Error: No PR found for current branch." >&2
    exit 1
fi

if [[ "$COMMENT_TYPE" == "issue" ]]; then
    # Reply to general PR comment (issue comment)
    gh api "repos/{owner}/{repo}/issues/${PR_NUMBER}/comments" \
        --method POST \
        --field body="${PREFIXED_RESPONSE}" \
        --jq '"Successfully posted reply (Comment ID: \(.id))"'
else
    # Reply to review comment (inline code comment)
    # Get the pull request review comment to find the right context
    gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/comments" \
        --method POST \
        --field body="${PREFIXED_RESPONSE}" \
        --field in_reply_to="${COMMENT_ID}" \
        --jq '"Successfully posted reply (Comment ID: \(.id))"'
fi

echo "Reply posted with [Claude Code] prefix."
