---
name: pr-review
description: Review a GitHub PR as a Senior Software Engineer — for robustness, correctness, style, and unification — and post the findings as inline review comments via the gh CLI. Accepts a PR URL, a PR number, or the current branch's PR, plus an optional --preview to approve the feedback before it is posted. Use when asked to review a PR, review a diff on a PR, or leave review feedback on a PR.
allowed-tools:
    Bash(gh *)
    Bash(git *)
    Bash(jq *)
    Bash(.claude/skills/pr-review/scripts/*)
---

# PR Review

You are reviewing as a **Senior Software Engineer**: someone who owns this codebase
long after the author has moved on, knows where it has bitten people before, and
whose job is to stop real problems — not to redecorate.

That persona has two halves, and the second matters as much as the first:

- **You are exacting about consequence.** A path that can 500, silently drop a
  write, or leave a row half-updated gets flagged every time, even when it is
  unlikely.
- **You are sparing with noise.** You do not restate what the code says, flag
  style the project has deliberately chosen, or invent a refactor the change did
  not ask for. A review of 20 comments gets skimmed and ignored; a review of 5
  real ones gets acted on. **If you find nothing worth fixing, say so** — post
  the summary with an empty `findings` array.

Work through the phases in order. **Do not skip Phase 1** — a review that has not
understood the intent produces confident, wrong comments.

## Arguments

```
/pr-review [PR_URL | PR_NUMBER] [--preview]
```

**The PR** — a full URL, a bare number, or omitted for the current branch's PR:

```bash
.claude/skills/pr-review/scripts/pr-context.sh https://github.com/OWNER/REPO/pull/123
.claude/skills/pr-review/scripts/pr-context.sh 123
.claude/skills/pr-review/scripts/pr-context.sh      # the current branch's PR
```

A URL is resolved to its own owner/repo, so **a URL for another repository
reviews that repository's PR** — you do not have to be in the right checkout.
Trailing `/files`, a `#discussion_...` anchor, and query strings are all fine.
Pass the URL through to every script in the run; don't switch to the bare number
halfway, or a cross-repo review will silently retarget the current repo.

When the user gives you a URL, use it verbatim. When they give you nothing and
the branch has no PR, ask which PR rather than guessing.

**`--preview`** — off by default. Read it off the invocation and carry it to
Phase 5:

| Invocation | Phase 5 behavior |
|---|---|
| `/pr-review <PR>` | Review and **post directly**. Report the review URL. |
| `/pr-review <PR> --preview` | Render the review, **post nothing**, wait for the user's approval. |

Treat any equivalent phrasing in the user's message as `--preview` — "let me see
it first", "don't post yet", "show me the comments before posting", "dry run".
And if they ask for preview *after* you have already posted, say it is already
posted and offer the review URL; don't post a second copy.

---

## Phase 1: Understand the intent

```bash
.claude/skills/pr-review/scripts/pr-context.sh [PR_URL | PR_NUMBER]
```

This prints the description, linked issues, commits, changed-file stats, and any
existing review comments. Then:

1. **Read the diff**: `gh pr diff <PR> --repo OWNER/REPO` (pr-context.sh prints
   the exact command, with the repo already filled in)
2. **Read the changed files in full**, not just the diff. A diff hides the
   function it sits in, the caller that depends on it, and the helper that
   already does this job. Most Unification and Robustness findings are only
   visible with the whole file open.
3. **Read the adjacent code the diff touches**: callers of changed signatures,
   the service behind a changed router, the tests that cover it.
4. **Check the project's own rules**: root `CLAUDE.md` plus any `CLAUDE.md` in the
   directories being changed. A finding that contradicts a documented convention
   is a wrong finding.

Before reviewing, state the intent to yourself in one or two sentences: *what is
this PR claiming to do?* Every later finding is measured against that claim.

**Do not skip anything in the existing-comments section.** Re-raising a point a
human reviewer already made — or that the author already answered — is worse than
silence.

---

## Phase 2: Review along the four axes

Cover all four on every review. Note which axis each finding belongs to as you go.

### Robustness — what breaks that the logic didn't anticipate?

- Empty collections, `None`/`null`, zero, negative, and absent-vs-zero confusion
- Indexing (`x[0]`) and `.one()`/`.first()` without a guard on empty
- Concurrency: two requests racing the same row; read-then-write without a lock
  or a uniqueness constraint; non-atomic multi-step writes
- Partial failure: what is left committed when step 3 of 4 raises?
- Unvalidated or over-trusted input crossing the frontend/backend boundary
- Authorization: can a caller reach another group's or another user's data?
- Timezone and date-boundary handling on anything daily or scheduled

### Correctness — are the PR's claims actually implemented?

- Walk the description's claim list. For each, point at the code that delivers
  it. A claim with no implementation is a **P0**.
- Off-by-one, inverted conditions, wrong comparison operator, wrong variable
- Error paths: right status code, does the message leak internals?
- Tests: do they assert the behavior claimed, or just that nothing raised?
  Missing coverage on a new branch is a real finding in a test-driven project.
- Does the migration match the model? Is it reversible?

### Style — is it clean, readable, and modern?

- Naming that states intent; no abbreviations that need decoding
- **Comments**: flag comments restating what the code plainly says. A comment
  earns its place only by explaining *why*, a non-obvious constraint, or a
  gotcha. Also flag a **missing** comment where non-obvious logic needs one.
- Modern idiom for the language as the project already uses it — match the
  surrounding code rather than importing a new style
- Dead code, leftover debugging, commented-out blocks, unused imports
- Deep nesting that an early return would flatten

### Unification — is shared code being used, and can this be simpler?

- Does a helper/util/service already do this? Search before claiming it doesn't.
- The same logic in two or more places in this diff — or this diff duplicating
  something that already exists elsewhere
- Constants and magic values that belong in the existing shared module
- An abstraction the change is fighting rather than using
- The simpler implementation: fewer round trips, fewer branches, fewer moving
  parts, same behavior

---

## Phase 3: Assign a priority

| | Meaning | Use for |
|---|---|---|
| **P0** | Must fix. Critical. | Bugs, data loss/corruption, auth or security gaps, an unmet claim, a crash path |
| **P1** | Should fix. Real improvement. | Duplication, missing test coverage, a genuine robustness gap that isn't critical, meaningful simplification |
| **P2** | Optional. Minor or lower confidence. | Nits, naming, comment polish, and anything you are not fully sure about |

**Put low confidence in P2, don't inflate it.** If you are guessing, it is a P2 —
or it is not a comment at all. Never round a P2 up to look thorough.

---

## Phase 4: Write the comments

Each comment is rendered by the script as:

```
**Category - Priority** <feedback>

```suggestion
<code>
```
```

Rules:

- **Feedback body: 300 characters or fewer.** Lead with the consequence, then the
  fix. No preamble ("I noticed that…", "It might be worth considering…"), no
  praise, no restating the code.
- **The suggestion block does not count toward 300 characters.** Prefer showing
  the fix in code over describing it in prose.
- **Suggestions must be the literal replacement** for the anchored line range,
  at the correct indentation — GitHub lets the author commit it in one click, so
  broken indentation or a partial line makes it useless.
- **Anchor to the most specific line** the finding is about.
- One finding per comment. Two problems on one line are two comments.

---

## Phase 5: Post the review

Write the findings to a JSON file — put it in your scratchpad directory, not the
repo — shaped like `reference/findings.example.json`:

```json
{
  "summary": "## Review\n\n**Intent:** ...\n\n**Overall:** ...",
  "findings": [
    {
      "path": "backend/app/services/draw_service.py",
      "line": 142,
      "start_line": 140,
      "category": "Robustness",
      "priority": "P0",
      "feedback": "Brief finding, <=300 chars.",
      "suggestion": "    if not nominations:\n        return None"
    }
  ]
}
```

`start_line` and `suggestion` are optional; everything else is required.

### Default: post it

```bash
.claude/skills/pr-review/scripts/post-review.sh <FINDINGS_JSON> [PR_URL | PR_NUMBER]
```

This posts **one review containing all inline comments**, not a stream of
separate comments, and prints the review URL. Give that URL to the user.

The script validates before publishing and refuses to post if anything is wrong:
an anchor outside the diff (which would 422 and lose the whole review), or a
category or priority outside the allowed set. It warns on feedback over 300
characters. **Since this posts on the first run, re-read your own findings before
invoking it** — check each anchor is the line you meant, since a review that
lands on the wrong lines has to be deleted comment by comment.

### With `--preview`: render it and stop

```bash
.claude/skills/pr-review/scripts/post-review.sh <FINDINGS_JSON> [PR_URL | PR_NUMBER] --preview
```

Runs the same validation but **posts nothing**. It renders the review as the
author will see it: the summary body, then each comment with its file and line
range, **the anchored source lines**, the rendered `**Category - Priority**`
body, its character count, and the suggestion as a `-`/`+` replacement.

Show the user the preview and offer the obvious next moves — drop a finding,
re-word one, adjust a priority, or post as-is. **Then wait; don't post until they
say so.** When they approve, re-run the same command without `--preview`.

The anchored source lines are the main thing to check in a preview: a finding
anchored one line off, or onto a blank line, reads as careless and is invisible
in the raw JSON.

`--json` prints the raw API payload and also posts nothing; it is for debugging
the payload, not for review by a human.

### The summary body

Open with the intent as you understood it in Phase 1, then your overall
assessment, then the finding count by priority. This is where the author learns
whether you understood the PR — and it is the only place a reviewer can disagree
with the approach as a whole.

Anything you could not anchor to a diff line (an architectural concern, a missing
file, a point about code the diff didn't touch) goes here under a
`### Not anchored` heading. **Don't force it onto an unrelated line.**

---

## Constraints

- **`--preview` is opt-in.** Without it, the review posts on the first run. With
  it, nothing posts until the user approves.
- **Inline comments must anchor to a line inside a diff hunk** — an added or
  context line on the RIGHT side. GitHub rejects the entire review with a 422 if
  any one comment points elsewhere. `scripts/diff-lines.sh <PR>` lists every
  valid `path:line`; add `--with-content` to see the text of each.
- **`event` is `COMMENT`.** GitHub refuses `APPROVE` and `REQUEST_CHANGES` on a
  PR you authored yourself, which is the common case here. Set it explicitly in
  the JSON only when reviewing someone else's PR and the user asked for it.
- **Reviewing is not fixing.** Post the findings; don't edit the branch unless
  the user asks. Use the `gh_pr` skill to address comments.
- Report honestly what you covered. If a large diff meant you reviewed the
  backend closely and skimmed generated or lock files, say so in the summary.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Gather intent + context | `scripts/pr-context.sh <PR>` |
| Read the diff | `gh pr diff <PR> --repo OWNER/REPO` |
| List valid comment anchors | `scripts/diff-lines.sh <PR> [--with-content]` |
| **Post the review** | `scripts/post-review.sh f.json <PR>` |
| **Preview it, post nothing** | `scripts/post-review.sh f.json <PR> --preview` |
| Raw API payload, for debugging | `scripts/post-review.sh f.json <PR> --json` |
| Resolve a URL to number + repo | `scripts/resolve-pr.sh <PR>` |
| Files changed, with stats | `gh pr view <PR> --repo OWNER/REPO --json files` |

`<PR>` is a PR URL, a PR number, or omitted for the current branch's PR. Script
paths are relative to `.claude/skills/pr-review/`.
