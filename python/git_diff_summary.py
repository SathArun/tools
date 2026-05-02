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
    cmd = [sys.executable, "-m", "llm"]
    if model_name:
        cmd += ["-m", model_name]
    result = subprocess.run(cmd, input=prompt, text=True, capture_output=True, encoding='utf-8')
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "No module named" in stderr:
            raise FileNotFoundError(stderr)
        raise RuntimeError(stderr)
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


def summarize_file(header, chunk, model_name=None):
    """Summarize a single file's diff in 1-2 sentences."""
    prompt = (
        "Summarize the changes to this file in 1-2 sentences, focusing on what"
        f" changed and why it matters:\n\n{chunk}"
    )
    return call_llm(prompt, model_name)


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
            with open(args.diff_file, encoding='utf-8') as f:
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
            if not file_summaries:
                print(
                    "Error: all per-file summaries failed — cannot synthesize.",
                    file=sys.stderr,
                )
                sys.exit(1)
            result = synthesize(file_summaries, args.model)
    except FileNotFoundError:
        # subprocess raises FileNotFoundError when the 'llm' binary is not on PATH
        print("llm not found — install with: pip install llm", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()
