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
