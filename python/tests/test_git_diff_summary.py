import sys
import os
import io
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import git_diff_summary  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

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
@@ -0,0 +1,2 @@
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


def test_call_llm_default_model():
    mock_result = MagicMock(returncode=0, stdout="feat: do thing\n\nExplanation here.")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = git_diff_summary.call_llm("some prompt")
    assert result == "feat: do thing\n\nExplanation here."
    cmd = mock_run.call_args[0][0]
    assert cmd == [sys.executable, "-m", "llm"]
    assert mock_run.call_args[1]["encoding"] == "utf-8"


def test_call_llm_with_model():
    mock_result = MagicMock(returncode=0, stdout="fix: patch bug\n\nDetails.")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = git_diff_summary.call_llm("some prompt", model_name="gpt-4o")
    assert result == "fix: patch bug\n\nDetails."
    cmd = mock_run.call_args[0][0]
    assert cmd == [sys.executable, "-m", "llm", "-m", "gpt-4o"]


def test_call_llm_failure_raises():
    mock_result = MagicMock(returncode=1, stderr="model not found")
    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="model not found"):
            git_diff_summary.call_llm("prompt")


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


def test_summarize_file_sends_chunk():
    with patch("git_diff_summary.call_llm", return_value="Added error handling.") as mock_llm:
        result = git_diff_summary.summarize_file(
            "diff --git a/auth.py b/auth.py", "chunk content", model_name=None
        )
    assert result == "Added error handling."
    prompt = mock_llm.call_args[0][0]
    assert "chunk content" in prompt
    assert "1-2 sentences" in prompt


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


def test_main_reads_stdin_small_diff(capsys):
    small_diff = open(os.path.join(FIXTURES, "small.diff")).read()
    expected_output = "feat: update hello\n\nReturns hello string."
    mock_stdin = io.StringIO(small_diff)
    mock_stdin.isatty = lambda: False
    with patch("sys.argv", ["git_diff_summary.py"]), \
         patch("sys.stdin", mock_stdin), \
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
    mock_stdin = io.StringIO(large_diff)
    mock_stdin.isatty = lambda: False
    with patch("sys.argv", ["git_diff_summary.py"]), \
         patch("sys.stdin", mock_stdin), \
         patch("git_diff_summary.summarize_file", return_value=per_file_summary), \
         patch("git_diff_summary.synthesize", return_value=synthesis) as mock_synth:
        git_diff_summary.main()
    captured = capsys.readouterr()
    assert captured.out.strip() == synthesis
    mock_synth.assert_called_once()


def test_main_empty_diff_exits_cleanly(capsys):
    mock_stdin = io.StringIO("")
    mock_stdin.isatty = lambda: False
    with patch("sys.argv", ["git_diff_summary.py"]), \
         patch("sys.stdin", mock_stdin):
        git_diff_summary.main()
    captured = capsys.readouterr()
    assert "No changes in diff" in captured.out


def test_main_no_stdin_no_file_exits_1(capsys):
    with patch("sys.argv", ["git_diff_summary.py"]), \
         patch("sys.stdin.isatty", return_value=True), \
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
    mock_stdin = io.StringIO(small_diff)
    mock_stdin.isatty = lambda: False
    with patch("sys.argv", ["git_diff_summary.py"]), \
         patch("sys.stdin", mock_stdin), \
         patch("subprocess.run", side_effect=FileNotFoundError("llm not found")), \
         pytest.raises(SystemExit) as exc:
        git_diff_summary.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "pip install llm" in captured.err


def test_main_synthesis_runtime_error_exits_1(capsys):
    large_diff = open(os.path.join(FIXTURES, "large.diff")).read()
    mock_stdin = io.StringIO(large_diff)
    mock_stdin.isatty = lambda: False
    with patch("sys.stdin", mock_stdin), \
         patch("sys.argv", ["git_diff_summary.py"]), \
         patch("git_diff_summary.summarize_file", return_value="summary"), \
         patch("git_diff_summary.synthesize", side_effect=RuntimeError("API error")), \
         pytest.raises(SystemExit) as exc:
        git_diff_summary.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "API error" in captured.err


def test_main_all_per_file_summaries_fail_exits_1(capsys):
    large_diff = open(os.path.join(FIXTURES, "large.diff")).read()
    mock_stdin = io.StringIO(large_diff)
    mock_stdin.isatty = lambda: False
    with patch("sys.stdin", mock_stdin), \
         patch("sys.argv", ["git_diff_summary.py"]), \
         patch("git_diff_summary.summarize_file", side_effect=RuntimeError("API error")), \
         pytest.raises(SystemExit) as exc:
        git_diff_summary.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "all per-file summaries failed" in captured.err


def test_main_per_file_warning_continues(capsys):
    # Two files: first fails, second succeeds — should warn but continue to synthesize
    two_file_diff = (
        "diff --git a/a.py b/a.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/a.py\n+++ b/a.py\n@@ -0,0 +1 @@\n+x = 1\n"
        "diff --git a/b.py b/b.py\n"
        "index 0000000..2222222 100644\n"
        "--- a/b.py\n+++ b/b.py\n@@ -0,0 +1 @@\n+y = 2\n"
    )
    mock_stdin = io.StringIO(two_file_diff)
    mock_stdin.isatty = lambda: False
    call_count = [0]

    def fake_summarize_file(header, chunk, model_name=None):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("first file failed")
        return "Added y variable."

    with patch("sys.stdin", mock_stdin), \
         patch("sys.argv", ["git_diff_summary.py", "--threshold", "5"]), \
         patch("git_diff_summary.summarize_file", side_effect=fake_summarize_file), \
         patch("git_diff_summary.synthesize", return_value="fix: add vars\n\nAdded x and y.") as mock_synth:
        git_diff_summary.main()

    captured = capsys.readouterr()
    assert "Warning" in captured.err
    mock_synth.assert_called_once()
    # synthesize receives only the successful summary
    summaries_arg = mock_synth.call_args[0][0]
    assert len(summaries_arg) == 1
