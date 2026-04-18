# compress_pdf.py — Implementation Plan

**Date:** 2026-04-18
**Branch:** `claude/pdf-compression-tool-plan-8fxFA`

## Tasks

- [x] PRD and SPEC approved
- [x] Create `python/compress_pdf.py`
  - `detect_ghostscript()` with Windows Program Files glob fallback
  - `compress_ghostscript()` via subprocess
  - `compress_pymupdf()` with Pillow image resampling + seen_xrefs dedup
  - `compress()` dispatch with GS→PyMuPDF fallback chain
  - `main()` with argparse, pre-flight validation, error handling
- [x] Create `python/tests/test_compress_pdf.py` (33 tests, all passing)
  - `TestDetectGhostscript` (6 tests)
  - `TestCompressGhostscript` (7 tests)
  - `TestCompressPymupdf` (5 tests)
  - `TestCompressDispatch` (4 tests)
  - `TestMain` (11 tests)
- [x] Create `docs/superpowers/specs/2026-04-18-compress-pdf-design.md`
- [x] All 33 tests passing with no external dependencies required

## Usage

```bash
# Basic compression (medium quality, auto-detects backend)
python compress_pdf.py large.pdf smaller.pdf

# Aggressive compression for email/sharing
python compress_pdf.py scan.pdf scan_small.pdf --level low

# High quality for printing
python compress_pdf.py report.pdf report_print.pdf --level high --verbose
```

## Install backends

```bash
# Option A: Install Ghostscript (best compression)
# Windows: https://ghostscript.com/releases/gsdnld.html
# Linux:   apt install ghostscript
# macOS:   brew install ghostscript

# Option B: pip fallback (no system install needed)
pip install pymupdf pillow
```
