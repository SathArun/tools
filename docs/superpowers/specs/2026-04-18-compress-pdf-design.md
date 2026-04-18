# compress_pdf.py — Design Spec

**Date:** 2026-04-18
**Tool:** `python/compress_pdf.py`
**Tests:** `python/tests/test_compress_pdf.py`

---

## Problem

PDF files produced by scanners, export pipelines, or document editors are frequently much larger than necessary. Users need a fast, scriptable CLI tool to reduce file size without installing a GUI application or navigating printer-driver settings.

---

## CLI Interface

```
python compress_pdf.py input.pdf output.pdf [--level {low,medium,high}] [--verbose]
```

| Argument | Default | Description |
|---|---|---|
| `input` | required | Source PDF path |
| `output` | required | Destination PDF path (parent dir must exist) |
| `--level` | `medium` | `low` = smallest file, `medium` = balanced/print-ready, `high` = best quality |
| `--verbose` | off | Print backend, level, and before/after sizes to stderr |

---

## Architecture

### Five logical sections

1. `detect_ghostscript() -> str | None` — find GS executable
2. `compress_ghostscript(input, output, level, gs_exe)` — GS backend
3. `compress_pymupdf(input, output, level)` — PyMuPDF + Pillow backend
4. `compress(input, output, level, verbose)` — auto-detect and dispatch
5. `main()` — argparse + pre-flight validation

### Dispatch flow

```
main()
  ├─ pre-flight: input exists & is file, output parent exists, paths differ
  └─ compress()
       ├─ detect_ghostscript() → found  ──► compress_ghostscript()
       └─ not found
               ├─ import fitz succeeds  ──► compress_pymupdf()
               └─ ImportError ──► "pip install pymupdf" hint → exit 1
```

If the detected GS executable raises `FileNotFoundError` at subprocess time (race condition), the tool silently falls back to PyMuPDF.

---

## Ghostscript Backend

### Level → `-dPDFSETTINGS`

| Level | `-dPDFSETTINGS` | Approx image DPI |
|---|---|---|
| `low` | `/screen` | 72 |
| `medium` | `/ebook` | 150 |
| `high` | `/printer` | 300 |

### Executable detection order

1. `shutil.which("gswin64c")`
2. `shutil.which("gswin32c")`
3. `shutil.which("gs")`
4. `glob("C:\Program Files\gs\gs*\bin\gswin64c.exe")` (sorted, last = highest version)
5. `glob("C:\Program Files\gs\gs*\bin\gswin32c.exe")`
6. Return `None`

---

## PyMuPDF Backend

Used when Ghostscript is not available. Requires `pip install pymupdf pillow`.

### Level → DPI + JPEG quality

| Level | DPI | JPEG quality |
|---|---|---|
| `low` | 72 | 60 |
| `medium` | 150 | 80 |
| `high` | 300 | 95 |

### Algorithm

1. Open PDF with `fitz.open()`
2. For each page, iterate image xrefs (track `seen_xrefs` to skip duplicates across pages)
3. Estimate original DPI: `(orig_width / page_width_pts) * 72`
4. Skip if already at or below target DPI
5. Resample with Pillow (`LANCZOS`), re-save as JPEG at target quality
6. Replace stream in-place with `doc.update_stream(xref, bytes)`
7. `doc.save(output, garbage=4, deflate=True, clean=True)`

Bad image data emits a `Warning:` to stderr and continues; processing never aborts on a single bad image.

---

## Error Handling

| Scenario | Exit | Message to stderr |
|---|---|---|
| Input not found | 1 | `Error: input file not found: <path>` |
| Input is a directory | 1 | `Error: input path is not a file: <path>` |
| Output parent dir missing | 1 | `Error: output directory does not exist: <dir>` |
| Same input and output | 1 | `Error: input and output paths must be different` |
| No backend available | 1 | `Error: no PDF backend found. Install Ghostscript or run: pip install pymupdf` |
| GS non-zero exit | 1 | `Error: Ghostscript failed: <stderr>` |
| GS binary vanished (FileNotFoundError) | — | Falls back to PyMuPDF silently |
| PyMuPDF cannot open PDF | 1 | `Error: could not open PDF: <message>` |
| Image resampling fails | warning | `Warning: skipping image xref <n> on page <p>: <message>` |
| Output unwritable | 1 | `Error: <exception message>` |

---

## Dependencies

| Dependency | Type | Required for |
|---|---|---|
| Ghostscript | OS install | GS backend (auto-detected) |
| `pymupdf` | `pip install pymupdf` | PyMuPDF fallback backend |
| `pillow` | `pip install pillow` | Image resampling in PyMuPDF path |
| Standard library only | — | Everything else |

---

## Platform Support

- **Windows:** Primary target. GS detected via `gswin64c`/`gswin32c` on PATH or under `C:\Program Files\gs\`.
- **Linux / macOS:** Fully supported. GS detected as `gs` on PATH.
