import os

header_tpl = "diff --git a/file{n}.py b/file{n}.py\nindex 0000000..1111111 100644\n--- a/file{n}.py\n+++ b/file{n}.py\n"
block = "@@ -0,0 +1,10 @@\n" + "\n".join(f"+line{i}" for i in range(10)) + "\n"

out = []
for n in range(40):  # 40 files × ~15 lines = ~600 lines
    out.append(header_tpl.format(n=n) + block)

fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(fixtures_dir, exist_ok=True)
with open(os.path.join(fixtures_dir, "large.diff"), "w") as f:
    f.write("".join(out))

line_count = sum(1 for _ in open(os.path.join(fixtures_dir, "large.diff")))
print(f"large.diff: {line_count} lines")
