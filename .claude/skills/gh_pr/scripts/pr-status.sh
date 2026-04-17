#!/usr/bin/env bash
#
# pr-status.sh - Get comprehensive PR status including checks and review state
#
# Usage: pr-status.sh [PR_NUMBER]
#
# Shows PR details, CI check status, review status, and pending comments.

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

echo "PR #${PR_NUMBER} Status"
echo "=========================================="

# Basic PR info
echo ""
echo "## Overview"
gh pr view "$PR_NUMBER" --json title,state,isDraft,mergeable,url --jq '
    "Title: \(.title)\n" +
    "State: \(.state)\n" +
    "Draft: \(.isDraft)\n" +
    "Mergeable: \(.mergeable)\n" +
    "URL: \(.url)"
'

# CI Checks
echo ""
echo "## CI Checks"
gh pr checks "$PR_NUMBER" 2>/dev/null || echo "No checks configured."

# Reviews
echo ""
echo "## Reviews"
gh pr view "$PR_NUMBER" --json reviews --jq '
    if .reviews | length == 0 then
        "No reviews yet."
    else
        .reviews[] | "\(.author.login): \(.state)"
    end
'

# Requested reviewers
echo ""
echo "## Requested Reviewers"
gh pr view "$PR_NUMBER" --json reviewRequests --jq '
    if .reviewRequests | length == 0 then
        "No pending review requests."
    else
        .reviewRequests[].login
    end
'

# Comment count
echo ""
echo "## Comments"
REVIEW_COMMENTS=$(gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/comments" --jq 'length' 2>/dev/null || echo "0")
ISSUE_COMMENTS=$(gh api "repos/{owner}/{repo}/issues/${PR_NUMBER}/comments" --jq 'length' 2>/dev/null || echo "0")
echo "Review comments (inline): ${REVIEW_COMMENTS}"
echo "General comments: ${ISSUE_COMMENTS}"

echo ""
echo "=========================================="
echo "Run '.claude/skills/gh_pr/scripts/get-pr-comments.sh' to see comment details."
