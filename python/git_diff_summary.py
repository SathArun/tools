#!/usr/bin/env python3
"""Summarize a git diff using an LLM via the llm CLI."""

import argparse
import subprocess
import sys


def parse_diff_files(diff_text):
    """Split a unified diff into per-file chunks.

    Splits on 'diff --git' headers so new files, deletions, and renames
    (where '--- a/' may be '/dev/null') are all handled correctly.

    Returns list of (header_line, chunk_text) tuples, skipping empty chunks.
    Note: chunk_text includes the header line as its first line, making each
    chunk a self-contained parseable diff suitable for passing to an LLM.
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


def call_llm(prompt, model_name=None):
    """Send a prompt to the llm CLI and return the stripped response text."""
    cmd = ["llm"]
    if model_name:
        cmd += ["-m", model_name]
    result = subprocess.run(cmd, input=prompt, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


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
