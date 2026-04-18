import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import git_diff_summary  # noqa: E402

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
