# tools

A collection of lightweight, single-file Python command-line utilities.

---

## Tools

### `compress_pdf.py` — PDF Compressor

Reduce the file size of a PDF while keeping it clear enough for printing.

Auto-detects [Ghostscript](https://ghostscript.com/) if installed; falls back to [PyMuPDF](https://pymupdf.readthedocs.io/) automatically — no configuration needed.

**Quick start**

```bash
python python/compress_pdf.py input.pdf output.pdf
```

**Options**

```
positional arguments:
  input                 path to source PDF
  output                path for compressed output PDF

options:
  --level {low,medium,high}
                        compression level: low (smallest), medium (default), high (best quality)
  --verbose             print backend, level, and file sizes to stderr
```

**Examples**

```bash
# Default — balanced quality, good for printing
python python/compress_pdf.py report.pdf report_small.pdf

# Smallest file (email / sharing)
python python/compress_pdf.py scan.pdf scan_email.pdf --level low

# Best quality (high-res print)
python python/compress_pdf.py brochure.pdf brochure_print.pdf --level high --verbose
```

**Dependencies**

Install at least one backend:

```bash
# Option A — Ghostscript (best compression; system install)
# Windows: https://ghostscript.com/releases/gsdnld.html
# Linux:   sudo apt install ghostscript
# macOS:   brew install ghostscript

# Option B — PyMuPDF + Pillow (pip only, no system install needed)
pip install pymupdf pillow
```

---

### `git_diff_summary.py` — Git Diff Summariser

Pipe a `git diff` into this tool and get back a conventional-commit message plus a plain-English explanation, powered by any LLM supported by the [`llm` CLI](https://llm.datasette.io/).

**Quick start**

```bash
git diff HEAD~1 | python python/git_diff_summary.py
```

**Options**

```
options:
  --model MODEL         LLM model to use (default: llm's configured default)
  --threshold N         line count above which per-file summarisation is used (default: 300)
  --file FILE           read diff from a file instead of stdin
```

**Examples**

```bash
# Summarise staged changes
git diff --cached | python python/git_diff_summary.py

# Use a specific model
git diff HEAD~3 | python python/git_diff_summary.py --model gpt-4o

# Read from a saved diff file
python python/git_diff_summary.py --file changes.diff
```

**Dependencies**

```bash
pip install llm
llm keys set openai   # or whichever provider you use
```

---

## Running tests

```bash
pip install pytest
pytest python/tests/ -v
```

---

## Repository layout

```
python/
  compress_pdf.py          # PDF compression tool
  git_diff_summary.py      # Git diff → commit message tool
  tests/                   # pytest suite for both tools
docs/
  superpowers/
    specs/                 # design specifications
    plans/                 # implementation plans
```
