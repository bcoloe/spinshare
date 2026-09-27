#!/usr/bin/env bash
#
# post-review.sh - Post findings as a single PR review
#
# Usage: post-review.sh <FINDINGS_JSON> [PR_URL | PR_NUMBER] [--preview|--json]
#
#   (default)  Validate and PUBLISH the review to the PR.
#   --preview  Render a human-readable preview instead. Posts nothing.
#   --json     Print the raw API payload instead. Posts nothing.
#
# Validation of anchors, categories and priorities runs in every mode; only the
# publish step is mode-dependent.
#
# FINDINGS_JSON is shaped like reference/findings.example.json:
#
#   {
#     "summary": "Markdown review body (intent restated + overall take).",
#     "findings": [
#       {
#         "path": "backend/app/services/draw_service.py",
#         "line": 142,              # anchor line, RIGHT side of the diff
#         "start_line": 140,        # optional, for a multi-line anchor
#         "category": "Robustness", # Robustness|Correctness|Style|Unification
#         "priority": "P0",         # P0|P1|P2
#         "feedback": "Brief finding, <=300 chars.",
#         "suggestion": "replacement code for the anchored lines"  # optional
#       }
#     ]
#   }
#
# Each comment renders as:
#   **Category - Priority**  <feedback>   [+ ```suggestion block```]
#
# Every anchor is validated against the diff first, because GitHub rejects the
# whole review (422) if any single comment points outside a diff hunk.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-pr.sh"

FINDINGS_FILE=""
PR_REF=""
MODE="post"

for arg in "$@"; do
    case "$arg" in
        --preview)           MODE="preview" ;;
        --json|--dry-run)    MODE="json" ;;
        --post)              MODE="post" ;;   # explicit form of the default
        -*)
            echo "Error: unknown flag ${arg}" >&2
            exit 1
            ;;
        *)
            if   [[ -z "$FINDINGS_FILE" ]]; then FINDINGS_FILE="$arg"
            elif [[ -z "$PR_REF" ]];        then PR_REF="$arg"
            fi
            ;;
    esac
done

if [[ -z "$FINDINGS_FILE" ]]; then
    echo "Usage: post-review.sh <FINDINGS_JSON> [PR_URL | PR_NUMBER] [--preview|--json]" >&2
    exit 1
fi

if [[ ! -f "$FINDINGS_FILE" ]]; then
    echo "Error: findings file not found: ${FINDINGS_FILE}" >&2
    exit 1
fi

if ! jq empty "$FINDINGS_FILE" 2>/dev/null; then
    echo "Error: ${FINDINGS_FILE} is not valid JSON." >&2
    exit 1
fi

IFS=$'\t' read -r PR_NUMBER PR_REPO < <(resolve_pr "$PR_REF")

# --- Validate required fields -------------------------------------------------

MISSING=$(jq -r '
    .findings // [] | to_entries[] |
    select(
        (.value.path // "") == "" or (.value.line // null) == null or
        (.value.category // "") == "" or (.value.priority // "") == "" or
        (.value.feedback // "") == ""
    ) | "  finding[\(.key)] is missing path, line, category, priority, or feedback"
' "$FINDINGS_FILE")

if [[ -n "$MISSING" ]]; then
    echo "Error: incomplete findings:" >&2
    echo "$MISSING" >&2
    exit 1
fi

BAD_ENUM=$(jq -r '
    .findings // [] | to_entries[] |
    select(
        ((.value.priority | ascii_upcase) as $p | ["P0","P1","P2"] | index($p) | not) or
        ((.value.category | ascii_downcase) as $c |
            ["robustness","correctness","style","unification"] | index($c) | not)
    ) |
    "  finding[\(.key)] \(.value.path):\(.value.line) has category=\(.value.category) priority=\(.value.priority)"
' "$FINDINGS_FILE")

if [[ -n "$BAD_ENUM" ]]; then
    echo "Error: category must be Robustness|Correctness|Style|Unification and priority P0|P1|P2:" >&2
    echo "$BAD_ENUM" >&2
    exit 1
fi

# --- Validate anchors against the diff ---------------------------------------

ANCHORS=$(mktemp)
trap 'rm -f "$ANCHORS"' EXIT
"${SCRIPT_DIR}/diff-lines.sh" "$PR_NUMBER" --with-content > "$ANCHORS"

if [[ ! -s "$ANCHORS" ]]; then
    echo "Error: could not read any diff lines for ${PR_REPO} PR #${PR_NUMBER}." >&2
    exit 1
fi

anchor_text() {  # path:line -> source text of that line
    grep -m1 -F "$1"$'\t' "$ANCHORS" 2>/dev/null | cut -f2- || true
}

anchor_valid() {
    cut -f1 "$ANCHORS" | grep -qxF "$1"
}

INVALID=""
while IFS=$'\t' read -r idx path line start_line; do
    checked=""
    for candidate in "$line" "$start_line"; do
        [[ "$candidate" == "null" || -z "$candidate" ]] && continue
        [[ " $checked " == *" $candidate "* ]] && continue
        checked+=" $candidate"
        if ! anchor_valid "${path}:${candidate}"; then
            INVALID+="  finding[${idx}] ${path}:${candidate} is not in the diff"$'\n'
        fi
    done
done < <(jq -r '.findings // [] | to_entries[] |
    [.key, .value.path, (.value.line|tostring), (.value.start_line // "" |tostring)] | @tsv' "$FINDINGS_FILE")

if [[ -n "$INVALID" ]]; then
    echo "Error: these comments would be rejected by GitHub:" >&2
    printf '%s' "$INVALID" >&2
    echo "" >&2
    echo "Inline comments must anchor to an added or context line inside a diff hunk." >&2
    echo "Run 'diff-lines.sh ${PR_NUMBER}' to list valid anchors, or move the point into .summary." >&2
    exit 1
fi

# --- Build the review payload ------------------------------------------------

# event: COMMENT is the default and the only one that always works. GitHub
# refuses APPROVE and REQUEST_CHANGES on a PR you authored yourself.
PAYLOAD=$(jq '{
    body: (.summary // ""),
    event: (.event // "COMMENT"),
    comments: [
        (.findings // [])[] | {
            path: .path,
            line: .line,
            side: "RIGHT",
            body: (
                "**" + .category + " - " + (.priority | ascii_upcase) + "** " + .feedback
                + (if (.suggestion // "") == "" then ""
                   else "\n\n```suggestion\n" + .suggestion + "\n```" end)
            )
        }
        + (if .start_line then {start_line: .start_line, start_side: "RIGHT"} else {} end)
    ]
}' "$FINDINGS_FILE")

COUNT=$(jq '.comments | length' <<<"$PAYLOAD")

if [[ "$MODE" == "json" ]]; then
    echo "--- API payload for ${PR_REPO} PR #${PR_NUMBER} (${COUNT} comments) - nothing posted ---"
    jq . <<<"$PAYLOAD"
    exit 0
fi

# --- Preview ------------------------------------------------------------------

if [[ "$MODE" == "preview" ]]; then
    PR_TITLE=$(gh pr view "$PR_NUMBER" --repo "$PR_REPO" --json title --jq '.title' 2>/dev/null || echo "?")
    P0=$(jq '[.findings[]? | select((.priority|ascii_upcase) == "P0")] | length' "$FINDINGS_FILE")
    P1=$(jq '[.findings[]? | select((.priority|ascii_upcase) == "P1")] | length' "$FINDINGS_FILE")
    P2=$(jq '[.findings[]? | select((.priority|ascii_upcase) == "P2")] | length' "$FINDINGS_FILE")

    echo "══════════════════════════════════════════════════════════════════════"
    echo "  REVIEW PREVIEW (--preview) - nothing has been posted"
    echo "  ${PR_REPO} PR #${PR_NUMBER}: ${PR_TITLE}"
    echo "  ${COUNT} inline comment(s) - ${P0} P0, ${P1} P1, ${P2} P2"
    echo "══════════════════════════════════════════════════════════════════════"
    echo ""
    echo "───── Summary comment ────────────────────────────────────────────────"
    jq -r '.summary // "(no summary provided)"' "$FINDINGS_FILE"
    echo ""

    if [[ "$COUNT" -eq 0 ]]; then
        echo "───── Inline comments ────────────────────────────────────────────────"
        echo "(none - this review reports no findings)"
    fi

    while IFS=$'\t' read -r n path line start_line category priority chars; do
        echo "───── ${n}. ${category} - ${priority} ───────────────────────────────────────"
        if [[ "$start_line" != "null" && -n "$start_line" ]]; then
            echo "  ${path}:${start_line}-${line}"
        else
            echo "  ${path}:${line}"
        fi
        echo ""

        # Show the anchored source lines so the reader can judge the anchor.
        first="${start_line}"
        [[ "$first" == "null" || -z "$first" ]] && first="$line"
        for (( ln=first; ln<=line; ln++ )); do
            printf '  %6d | %s\n' "$ln" "$(anchor_text "${path}:${ln}")"
        done
        echo ""

        jq -r --argjson i "$((n-1))" '
            .findings[$i] |
            "**" + .category + " - " + (.priority|ascii_upcase) + "** " + .feedback
        ' "$FINDINGS_FILE" | fold -s -w 76 | sed 's/^/  /'

        if [[ "$chars" -gt 300 ]]; then
            echo "  ^^ OVER LIMIT: feedback is ${chars} chars (max 300)"
        else
            echo "  (feedback: ${chars} chars)"
        fi

        SUGG=$(jq -r --argjson i "$((n-1))" '.findings[$i].suggestion // ""' "$FINDINGS_FILE")
        if [[ -n "$SUGG" ]]; then
            echo ""
            echo "  Suggested replacement:"
            for (( ln=first; ln<=line; ln++ )); do
                printf '  - %s\n' "$(anchor_text "${path}:${ln}")"
            done
            printf '%s\n' "$SUGG" | sed 's/^/  + /'
        fi
        echo ""
    done < <(jq -r '.findings // [] | to_entries[] |
        [(.key + 1), .value.path, (.value.line|tostring),
         (.value.start_line // "null" |tostring), .value.category,
         (.value.priority|ascii_upcase), (.value.feedback|length)] | @tsv' "$FINDINGS_FILE")

    echo "══════════════════════════════════════════════════════════════════════"
    echo "  Nothing was posted. To publish this review as-is, drop --preview:"
    echo ""
    echo "    ${0} ${FINDINGS_FILE} ${PR_NUMBER}"
    echo "══════════════════════════════════════════════════════════════════════"
    exit 0
fi

# --- Post ---------------------------------------------------------------------

echo "Posting review with ${COUNT} inline comment(s) to ${PR_REPO} PR #${PR_NUMBER}..."

jq . <<<"$PAYLOAD" | gh api "repos/${PR_REPO}/pulls/${PR_NUMBER}/reviews" \
    --method POST --input - \
    --jq '"Review posted: \(.html_url)"'
