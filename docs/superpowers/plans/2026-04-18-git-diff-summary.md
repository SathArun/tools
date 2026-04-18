# git_diff_summary.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-file Python CLI that pipes a `git diff` through an LLM and outputs a conventional-commits message plus a plain-English explanation.

**Architecture:** Reads a unified diff from stdin or `--file`, checks line count against a threshold (default 300), and either summarizes in one LLM call (small diffs) or splits by `diff --git` headers, summarizes each file independently, then synthesizes a final result (large diffs). All LLM calls go through the `llm` CLI via `subprocess`.

**Tech Stack:** Python 3 stdlib only (`argparse`, `subprocess`, `sys`), plus [`llm`](https://llm.datasette.io) CLI installed in PATH.

---

## File Structure

```
tools/
  python/
    git_diff_summary.py          # single-file CLI tool
    tests/
      test_git_diff_summary.py   # pytest test suite
      fixtures/
        small.diff               # <300 line diff fixture
        large.diff               # >300 line diff fixture (multi-file)
```

---

### Task 1: Project scaffold

**Files:**
- Create: `tools/python/git_diff_summary.py`
- Create: `tools/python/tests/__init__.py`
- Create: `tools/python/tests/test_git_diff_summary.py`

- [ ] **Step 1: Create the main script skeleton**

`tools/python/git_diff_summary.py`:
```python
#!/usr/bin/env python3
"""Summarize a git diff using an LLM via the llm CLI."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Summarize a git diff using an LLM.",
        epilog="Example: git diff HEAD~1 | python git_diff_summary.py",
    )
    parser.add_argument(
        "--model", help="LLM model to use (default: llm's configured default)"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=300,
        help="Line count above which per-file summarization is used (default: 300)",
    )
    parser.add_argument(
        "--file",
        dest="diff_file",
        metavar="FILE",
        help="Read diff from file instead of stdin",
    )
    args = parser.parse_args()
    print(f"args: {args}")  # temporary


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create test scaffold**

`tools/python/tests/__init__.py` — empty file.

`tools/python/tests/test_git_diff_summary.py`:
```python
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import git_diff_summary  # noqa: E402
```

- [ ] **Step 3: Verify import works**

```bash
cd tools/python && python -c "import tests.test_git_diff_summary; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit scaffold**

```bash
cd tools
git init
git add python/git_diff_summary.py python/tests/__init__.py python/tests/test_git_diff_summary.py
git commit -m "chore: scaffold git_diff_summary.py with argparse and test import"
```

---

### Task 2: Diff file parser

**Files:**
- Modify: `tools/python/git_diff_summary.py`
- Modify: `tools/python/tests/test_git_diff_summary.py`

- [ ] **Step 1: Write the failing test**

Add to `tools/python/tests/test_git_diff_summary.py`:
```python
SMALL_DIFF = """\
diff --git a/foo.py b/foo.py
index 1234567..abcdefg 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def hello():
-    pass
+    return "hello"
+
diff --git a/bar.py b/bar.py
index 0000000..1111111 100644
--- a/bar.py
+++ b/bar.py
@@ -0,0 +1,2 @@
+def world():
+    return "world"
"""

NEW_FILE_DIFF = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def new():
+    pass
"""


def test_parse_diff_files_two_files():
    chunks = git_diff_summary.parse_diff_files(SMALL_DIFF)
    assert len(chunks) == 2
    assert chunks[0][0] == "diff --git a/foo.py b/foo.py"
    assert "def hello" in chunks[0][1]
    assert chunks[1][0] == "diff --git a/bar.py b/bar.py"
    assert "def world" in chunks[1][1]


def test_parse_diff_files_new_file():
    chunks = git_diff_summary.parse_diff_files(NEW_FILE_DIFF)
    assert len(chunks) == 1
    assert chunks[0][0] == "diff --git a/new.py b/new.py"
    assert "/dev/null" in chunks[0][1]


def test_parse_diff_files_empty():
    assert git_diff_summary.parse_diff_files("") == []
    assert git_diff_summary.parse_diff_files("   \n  ") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "parse_diff"
```
Expected: `AttributeError: module 'git_diff_summary' has no attribute 'parse_diff_files'`

- [ ] **Step 3: Implement `parse_diff_files`**

Add to `tools/python/git_diff_summary.py` (before `main`):
```python
def parse_diff_files(diff_text):
    """Split a unified diff into per-file chunks.

    Splits on 'diff --git' headers so new files, deletions, and renames
    (where '--- a/' may be '/dev/null') are all handled correctly.

    Returns list of (header_line, chunk_text) tuples, skipping empty chunks.
    """
    chunks = []
    current_header = None
    current_lines = []

    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current_header is not None:
                chunk = "".join(current_lines)
                if chunk.strip():
                    chunks.append((current_header, chunk))
            current_header = line.rstrip("\n")
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_header is not None:
        chunk = "".join(current_lines)
        if chunk.strip():
            chunks.append((current_header, chunk))

    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "parse_diff"
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd tools
git add python/git_diff_summary.py python/tests/test_git_diff_summary.py
git commit -m "feat: add diff file parser splitting on diff --git headers"
```

---

### Task 3: LLM caller via subprocess

**Files:**
- Modify: `tools/python/git_diff_summary.py`
- Modify: `tools/python/tests/test_git_diff_summary.py`

- [ ] **Step 1: Write the failing tests**

Add to `tools/python/tests/test_git_diff_summary.py`:
```python
from unittest.mock import patch, MagicMock


def test_call_llm_default_model():
    mock_result = MagicMock(returncode=0, stdout="feat: do thing\n\nExplanation here.")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = git_diff_summary.call_llm("some prompt")
    assert result == "feat: do thing\n\nExplanation here."
    cmd = mock_run.call_args[0][0]
    assert cmd == ["llm"]


def test_call_llm_with_model():
    mock_result = MagicMock(returncode=0, stdout="fix: patch bug\n\nDetails.")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = git_diff_summary.call_llm("some prompt", model_name="gpt-4o")
    assert result == "fix: patch bug\n\nDetails."
    cmd = mock_run.call_args[0][0]
    assert cmd == ["llm", "-m", "gpt-4o"]


def test_call_llm_failure_raises():
    mock_result = MagicMock(returncode=1, stderr="model not found")
    with patch("subprocess.run", return_value=mock_result):
        try:
            git_diff_summary.call_llm("prompt")
            assert False, "should have raised"
        except RuntimeError as e:
            assert "model not found" in str(e)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "call_llm"
```
Expected: `AttributeError: module 'git_diff_summary' has no attribute 'call_llm'`

- [ ] **Step 3: Implement `call_llm`**

Add to `tools/python/git_diff_summary.py` (after `parse_diff_files`, before `main`):
```python
import subprocess


def call_llm(prompt, model_name=None):
    """Send a prompt to the llm CLI and return the stripped response text."""
    cmd = ["llm"]
    if model_name:
        cmd += ["-m", model_name]
    result = subprocess.run(cmd, input=prompt, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()
```

Move the `import subprocess` to the top of the file with the other imports.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "call_llm"
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd tools
git add python/git_diff_summary.py python/tests/test_git_diff_summary.py
git commit -m "feat: add call_llm wrapper around llm CLI via subprocess"
```

---

### Task 4: Single-pass summarizer

**Files:**
- Modify: `tools/python/git_diff_summary.py`
- Modify: `tools/python/tests/test_git_diff_summary.py`

- [ ] **Step 1: Write the failing test**

Add to `tools/python/tests/test_git_diff_summary.py`:
```python
def test_summarize_single_passes_full_diff():
    expected = "feat: rewrite auth\n\nReplaced legacy token logic."
    with patch("git_diff_summary.call_llm", return_value=expected) as mock_llm:
        result = git_diff_summary.summarize_single("diff text here", model_name="claude-3")
    assert result == expected
    prompt = mock_llm.call_args[0][0]
    assert "conventional commits" in prompt
    assert "diff text here" in prompt
    assert mock_llm.call_args[0][1] == "claude-3"


def test_summarize_single_no_model():
    with patch("git_diff_summary.call_llm", return_value="fix: typo\n\nFixed.") as mock_llm:
        git_diff_summary.summarize_single("diff")
    assert mock_llm.call_args[0][1] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "summarize_single"
```
Expected: `AttributeError: module 'git_diff_summary' has no attribute 'summarize_single'`

- [ ] **Step 3: Implement `summarize_single`**

Add to `tools/python/git_diff_summary.py` (after `call_llm`):
```python
def summarize_single(diff_text, model_name=None):
    """Summarize an entire diff in one LLM call (used for small diffs)."""
    prompt = (
        "Given these git diff changes, output exactly two parts separated by a blank line:\n"
        "1) A git commit message using conventional commits format (subject ≤72 chars,"
        " optional bullet body if there are multiple distinct changes).\n"
        "2) A 2-3 sentence plain-English explanation of what changed and why.\n\n"
        f"Changes:\n{diff_text}"
    )
    return call_llm(prompt, model_name)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "summarize_single"
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd tools
git add python/git_diff_summary.py python/tests/test_git_diff_summary.py
git commit -m "feat: add single-pass summarizer for small diffs"
```

---

### Task 5: Per-file summarizer

**Files:**
- Modify: `tools/python/git_diff_summary.py`
- Modify: `tools/python/tests/test_git_diff_summary.py`

- [ ] **Step 1: Write the failing test**

Add to `tools/python/tests/test_git_diff_summary.py`:
```python
def test_summarize_file_sends_chunk():
    with patch("git_diff_summary.call_llm", return_value="Added error handling.") as mock_llm:
        result = git_diff_summary.summarize_file(
            "diff --git a/auth.py b/auth.py", "chunk content", model_name=None
        )
    assert result == "Added error handling."
    prompt = mock_llm.call_args[0][0]
    assert "chunk content" in prompt
    assert "1-2 sentences" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "summarize_file"
```
Expected: `AttributeError: module 'git_diff_summary' has no attribute 'summarize_file'`

- [ ] **Step 3: Implement `summarize_file`**

Add to `tools/python/git_diff_summary.py` (after `summarize_single`):
```python
def summarize_file(header, chunk, model_name=None):
    """Summarize a single file's diff in 1-2 sentences."""
    prompt = (
        "Summarize the changes to this file in 1-2 sentences, focusing on what"
        f" changed and why it matters:\n\n{chunk}"
    )
    return call_llm(prompt, model_name)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "summarize_file"
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
cd tools
git add python/git_diff_summary.py python/tests/test_git_diff_summary.py
git commit -m "feat: add per-file summarizer for large diff path"
```

---

### Task 6: Multi-file synthesizer

**Files:**
- Modify: `tools/python/git_diff_summary.py`
- Modify: `tools/python/tests/test_git_diff_summary.py`

- [ ] **Step 1: Write the failing test**

Add to `tools/python/tests/test_git_diff_summary.py`:
```python
def test_synthesize_combines_summaries():
    summaries = [
        ("diff --git a/auth.py b/auth.py", "Replaced token logic with JWT."),
        ("diff --git a/routes.py b/routes.py", "Added /login and /logout routes."),
    ]
    expected = "feat: add JWT authentication\n\nReplaced legacy tokens with JWT."
    with patch("git_diff_summary.call_llm", return_value=expected) as mock_llm:
        result = git_diff_summary.synthesize(summaries, model_name=None)
    assert result == expected
    prompt = mock_llm.call_args[0][0]
    assert "Replaced token logic with JWT" in prompt
    assert "Added /login and /logout routes" in prompt
    assert "conventional commits" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "synthesize"
```
Expected: `AttributeError: module 'git_diff_summary' has no attribute 'synthesize'`

- [ ] **Step 3: Implement `synthesize`**

Add to `tools/python/git_diff_summary.py` (after `summarize_file`):
```python
def synthesize(file_summaries, model_name=None):
    """Given per-file summaries, produce final commit message and explanation."""
    summaries_text = "\n".join(
        f"- {header}: {summary}" for header, summary in file_summaries
    )
    prompt = (
        "Given these per-file change summaries, output exactly two parts separated"
        " by a blank line:\n"
        "1) A git commit message using conventional commits format (subject ≤72 chars,"
        " optional bullet body if there are multiple distinct changes).\n"
        "2) A 2-3 sentence plain-English explanation of what changed and why.\n\n"
        f"Changes:\n{summaries_text}"
    )
    return call_llm(prompt, model_name)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "synthesize"
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
cd tools
git add python/git_diff_summary.py python/tests/test_git_diff_summary.py
git commit -m "feat: add multi-file synthesizer for large diff path"
```

---

### Task 7: Main function — input reading and error handling

**Files:**
- Modify: `tools/python/git_diff_summary.py`
- Modify: `tools/python/tests/test_git_diff_summary.py`
- Create: `tools/python/tests/fixtures/small.diff`
- Create: `tools/python/tests/fixtures/large.diff`

- [ ] **Step 1: Create diff fixtures**

`tools/python/tests/fixtures/small.diff` (8 lines — well under 300):
```
diff --git a/hello.py b/hello.py
index 1234567..abcdefg 100644
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,4 @@
 def hello():
-    pass
+    return "hello"
```

`tools/python/tests/fixtures/large.diff` — generate a diff with >300 lines by repeating a block. Create `tools/python/tests/make_large_diff.py` and run once:
```python
import os

header = "diff --git a/file{n}.py b/file{n}.py\nindex 0000000..1111111 100644\n--- a/file{n}.py\n+++ b/file{n}.py\n"
block = "@@ -0,0 +1,10 @@\n" + "\n".join(f"+line{i}" for i in range(10)) + "\n"

out = []
for n in range(40):  # 40 files × ~15 lines = 600 lines
    out.append(header.format(n=n) + block)

os.makedirs(os.path.join(os.path.dirname(__file__), "fixtures"), exist_ok=True)
with open(os.path.join(os.path.dirname(__file__), "fixtures", "large.diff"), "w") as f:
    f.write("".join(out))

print(f"large.diff: {sum(1 for _ in open('tests/fixtures/large.diff'))} lines")
```

Run: `cd tools/python && python tests/make_large_diff.py`

- [ ] **Step 2: Write failing tests for main**

Add to `tools/python/tests/test_git_diff_summary.py`:
```python
import io
from unittest.mock import patch, MagicMock
import pytest


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_main_reads_stdin_small_diff(capsys):
    small_diff = open(os.path.join(FIXTURES, "small.diff")).read()
    expected_output = "feat: update hello\n\nReturns hello string."
    with patch("sys.stdin", io.StringIO(small_diff)), \
         patch("sys.stdin.isatty", return_value=False), \
         patch("git_diff_summary.summarize_single", return_value=expected_output) as mock_single, \
         patch("git_diff_summary.synthesize") as mock_synth:
        git_diff_summary.main()
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_output
    mock_single.assert_called_once()
    mock_synth.assert_not_called()


def test_main_large_diff_uses_per_file_path(capsys):
    large_diff = open(os.path.join(FIXTURES, "large.diff")).read()
    per_file_summary = "Changed lines in file."
    synthesis = "refactor: update generated files\n\nBulk update."
    with patch("sys.stdin", io.StringIO(large_diff)), \
         patch("sys.stdin.isatty", return_value=False), \
         patch("git_diff_summary.summarize_file", return_value=per_file_summary), \
         patch("git_diff_summary.synthesize", return_value=synthesis) as mock_synth:
        git_diff_summary.main()
    captured = capsys.readouterr()
    assert captured.out.strip() == synthesis
    mock_synth.assert_called_once()


def test_main_empty_diff_exits_cleanly(capsys):
    with patch("sys.stdin", io.StringIO("")), \
         patch("sys.stdin.isatty", return_value=False):
        git_diff_summary.main()
    captured = capsys.readouterr()
    assert "No changes in diff" in captured.out


def test_main_no_stdin_no_file_exits_1(capsys):
    with patch("sys.stdin.isatty", return_value=True), \
         pytest.raises(SystemExit) as exc:
        git_diff_summary.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "stdin" in captured.err or "file" in captured.err


def test_main_reads_from_file(tmp_path, capsys):
    diff_file = tmp_path / "test.diff"
    small_diff = open(os.path.join(FIXTURES, "small.diff")).read()
    diff_file.write_text(small_diff)
    expected = "feat: update\n\nExplanation."
    with patch("sys.argv", ["git_diff_summary.py", "--file", str(diff_file)]), \
         patch("git_diff_summary.summarize_single", return_value=expected):
        git_diff_summary.main()
    captured = capsys.readouterr()
    assert captured.out.strip() == expected


def test_main_llm_not_installed_exits_1(capsys):
    small_diff = open(os.path.join(FIXTURES, "small.diff")).read()
    with patch("sys.stdin", io.StringIO(small_diff)), \
         patch("sys.stdin.isatty", return_value=False), \
         patch("subprocess.run", side_effect=FileNotFoundError("llm not found")), \
         pytest.raises(SystemExit) as exc:
        git_diff_summary.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "pip install llm" in captured.err
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v -k "main"
```
Expected: multiple failures (main doesn't read stdin or handle errors yet)

- [ ] **Step 4: Implement `main`**

Replace the temporary `main()` in `tools/python/git_diff_summary.py` with:
```python
def main():
    parser = argparse.ArgumentParser(
        description="Summarize a git diff using an LLM.",
        epilog="Example: git diff HEAD~1 | python git_diff_summary.py",
    )
    parser.add_argument(
        "--model", help="LLM model to use (default: llm's configured default)"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=300,
        help="Line count above which per-file summarization is used (default: 300)",
    )
    parser.add_argument(
        "--file",
        dest="diff_file",
        metavar="FILE",
        help="Read diff from file instead of stdin",
    )
    args = parser.parse_args()

    if args.diff_file:
        try:
            with open(args.diff_file) as f:
                diff_text = f.read()
        except FileNotFoundError:
            print(f"Error: file not found: {args.diff_file}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        diff_text = sys.stdin.read()
    else:
        print(
            "Error: provide a diff via stdin or --file\n"
            "Example: git diff HEAD~1 | python git_diff_summary.py",
            file=sys.stderr,
        )
        sys.exit(1)

    if not diff_text.strip():
        print("No changes in diff.")
        return

    line_count = diff_text.count("\n")

    try:
        if line_count <= args.threshold:
            result = summarize_single(diff_text, args.model)
        else:
            chunks = parse_diff_files(diff_text)
            file_summaries = []
            for header, chunk in chunks:
                try:
                    summary = summarize_file(header, chunk, args.model)
                    file_summaries.append((header, summary))
                except RuntimeError as e:
                    print(f"Warning: failed to summarize {header}: {e}", file=sys.stderr)
            result = synthesize(file_summaries, args.model)
    except FileNotFoundError:
        print("llm not found — install with: pip install llm", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(result)
```

- [ ] **Step 5: Run all tests**

```bash
cd tools/python && python -m pytest tests/test_git_diff_summary.py -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
cd tools
git add python/git_diff_summary.py python/tests/test_git_diff_summary.py \
        python/tests/fixtures/small.diff python/tests/fixtures/large.diff \
        python/tests/make_large_diff.py
git commit -m "feat: implement main with adaptive single/per-file path and error handling"
```

---

### Task 8: End-to-end smoke test

**Files:**
- No changes — manual verification only

- [ ] **Step 1: Install llm if not present**

```bash
pip install llm
llm --version
```
Expected: prints version string

- [ ] **Step 2: Smoke test small diff via stdin**

```bash
cd tools/python
cat tests/fixtures/small.diff | python git_diff_summary.py
```
Expected: a conventional-commits message followed by a blank line and 2-3 sentence explanation.

- [ ] **Step 3: Smoke test large diff via stdin**

```bash
cd tools/python
cat tests/fixtures/large.diff | python git_diff_summary.py
```
Expected: synthesized commit message and explanation. May take longer (multiple LLM calls).

- [ ] **Step 4: Smoke test --file flag**

```bash
cd tools/python
python git_diff_summary.py --file tests/fixtures/small.diff
```
Expected: same output as Step 2.

- [ ] **Step 5: Smoke test empty diff**

```bash
echo "" | python tools/python/git_diff_summary.py
```
Expected: `No changes in diff.`

- [ ] **Step 6: Smoke test no input**

```bash
cd tools/python
python git_diff_summary.py
```
Expected: error message referencing stdin/--file, exit code 1.

- [ ] **Step 7: Smoke test against a real repo diff**

```bash
# Run inside any git repo with recent commits
git diff HEAD~1 | python /c/Arun/experiment/tools/python/git_diff_summary.py
```
Expected: a commit message and explanation describing the actual changes.

- [ ] **Step 8: Final commit**

```bash
cd tools
git add .
git commit -m "chore: verify end-to-end smoke tests pass"
```

---

## Self-Review

**Spec coverage:**
- ✅ Reads from stdin or `--file`
- ✅ Adaptive threshold (default 300 lines)
- ✅ Single-pass for small diffs
- ✅ Per-file summaries + synthesis for large diffs
- ✅ `--model` flag passed through to `llm`
- ✅ `--threshold` configurable
- ✅ Conventional commits output format
- ✅ Blank line separator + 2-3 sentence explanation
- ✅ Empty diff → clean exit
- ✅ No stdin + no `--file` → exit 1 with hint
- ✅ `llm` not installed → exit 1 with install hint
- ✅ Per-file failure → warning, continue
- ✅ Diff splitting on `diff --git` headers (handles `/dev/null`)

**No placeholders found.**

**Type consistency:** `call_llm(prompt, model_name)` signature used consistently across `summarize_single`, `summarize_file`, `synthesize`, and all tests. `parse_diff_files` returns `list[tuple[str, str]]` consumed correctly in `main` and `synthesize`.
