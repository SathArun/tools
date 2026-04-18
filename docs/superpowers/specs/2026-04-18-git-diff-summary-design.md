# Design: git_diff_summary.py

**Date:** 2026-04-18
**Status:** Approved

## Overview

A single-file Python CLI tool that pipes a `git diff` through an LLM (via Simon Willison's `llm` library) and outputs a conventional-commits-style commit message plus a plain-English explanation of the changes.

## Architecture

### Adaptive single/two-stage pipeline

```
stdin / --file
      │
      ▼
  read full diff
      │
      ├─ ≤ threshold lines ──► single LLM call → commit message + explanation
      │
      └─ > threshold lines
              │
              ▼
      split diff by file (parse "--- a/..." / "+++ b/..." headers)
              │
              ▼
      one llm call per file → 1-2 sentence summary
              │
              ▼
      combine summaries into synthesis prompt
              │
              ▼
      single final llm call → commit message + explanation
              │
              ▼
           stdout
```

Small diffs (under `--threshold` lines, default 300) skip the per-file stage entirely for speed. Large diffs summarize each changed file independently before synthesizing.

## CLI Interface

```
git diff HEAD~1            | python git_diff_summary.py
git diff --staged          | python git_diff_summary.py --model gpt-4o
git diff HEAD~5            | python git_diff_summary.py --threshold 500
python git_diff_summary.py --file my.patch
```

### Arguments

| Flag | Default | Description |
|---|---|---|
| `--model` | llm default | Model identifier passed directly to `llm` |
| `--threshold` | `300` | Line count above which per-file summarization kicks in |
| `--file` | stdin | Read diff from file instead of stdin |

## Output Format

```
feat: add user authentication middleware

- extracts token validation into standalone module
- adds rate limiting per user on /api/* routes

The auth middleware was tightly coupled to the request handler. This
separates token validation into its own module, making it testable
independently. Rate limiting is applied per-user rather than per-IP
to prevent shared-IP false positives.
```

- Subject line: conventional commits format (`feat:`, `fix:`, `refactor:`, etc.), ≤ 72 characters
- Optional bullet body for commits with multiple distinct changes
- Blank line separator between commit message and explanation
- Explanation: 2–3 sentences, plain English, focuses on what changed and why

## Prompts

**Per-file summary (large-diff path only):**
```
Summarize the changes to this file in 1-2 sentences, focusing on what
changed and why it matters:

{file_diff_chunk}
```

**Single-pass / final synthesis:**
```
Given these git diff changes, output exactly two parts separated by a
blank line:
1) A git commit message using conventional commits format (subject ≤72
   chars, optional bullet body if multiple distinct changes).
2) A 2-3 sentence plain-English explanation of what changed and why.

Changes:
{diff_or_per_file_summaries}
```

## Diff Parsing

Split raw diff text on lines beginning with `diff --git` to isolate per-file chunks (this correctly handles new files, deleted files, and renames where `--- a/` may be `/dev/null`). Each chunk runs from one `diff --git` header to the next. Binary file notices and empty chunks are skipped.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Empty diff | Print `No changes in diff.` to stdout, exit 0 |
| No stdin and no `--file` | Print usage hint to stderr, exit 1 |
| `llm` not installed | `llm not found — install with: pip install llm`, exit 1 |
| Per-file LLM call fails | Re-raise with filename included in error message |
| Final synthesis call fails | Re-raise with full error, exit 1 |

## Dependencies

- [`llm`](https://llm.datasette.io) — the only external dependency
- Standard library: `argparse`, `sys`, `subprocess` (none needed — input is piped)

## Testing

Manual test cases:
1. Small diff (`git diff HEAD~1` on a 1-file change) → single-pass path
2. Large diff (> 300 lines, multiple files) → per-file path
3. Empty diff (`git diff` with no changes) → graceful exit
4. `--model` flag overrides default model
5. `--file` reads from disk instead of stdin
