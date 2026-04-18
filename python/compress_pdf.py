#!/usr/bin/env python3
"""Compress a PDF file using Ghostscript (if installed) or PyMuPDF as a fallback."""

import argparse
import glob
import io
import os
import shutil
import subprocess
import sys

PDFSETTINGS = {
    "low": "/screen",
    "medium": "/ebook",
    "high": "/printer",
}

DPI_TARGETS = {"low": 72, "medium": 150, "high": 300}
JPEG_QUALITY = {"low": 60, "medium": 80, "high": 95}


def detect_ghostscript():
    """Return path to Ghostscript executable, or None if not found."""
    for name in ("gswin64c", "gswin32c", "gs"):
        path = shutil.which(name)
        if path:
            return path
    for pattern in (
        r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs*\bin\gswin32c.exe",
    ):
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    return None


def compress_ghostscript(input_path, output_path, level, gs_exe):
    """Compress PDF using Ghostscript subprocess."""
    cmd = [
        gs_exe,
        "-sDEVICE=pdfwrite",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        f"-dPDFSETTINGS={PDFSETTINGS[level]}",
        f"-sOutputFile={output_path}",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Ghostscript failed with no output")


def compress_pymupdf(input_path, output_path, level):
    """Compress PDF using PyMuPDF with image resampling via Pillow."""
    import fitz
    from PIL import Image

    target_dpi = DPI_TARGETS[level]
    quality = JPEG_QUALITY[level]

    doc = fitz.open(input_path)
    seen_xrefs = set()

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_width_pts = page.rect.width

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                orig_width = base_image["width"]

                approx_dpi = (orig_width / page_width_pts) * 72 if page_width_pts > 0 else target_dpi
                if approx_dpi <= target_dpi:
                    continue

                scale = target_dpi / approx_dpi
                new_width = max(1, int(orig_width * scale))
                new_height = max(1, int(base_image["height"] * scale))

                pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                doc.update_stream(xref, buf.getvalue())
            except Exception as e:
                print(
                    f"Warning: skipping image xref {xref} on page {page_index}: {e}",
                    file=sys.stderr,
                )

    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()


def _fmt_size(path):
    size = os.path.getsize(path)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def compress(input_path, output_path, level, verbose):
    """Detect backend and compress the PDF."""
    gs_exe = detect_ghostscript()

    if gs_exe:
        try:
            compress_ghostscript(input_path, output_path, level, gs_exe)
        except FileNotFoundError:
            gs_exe = None

    if not gs_exe:
        try:
            import fitz  # noqa: F401
        except ImportError:
            raise ImportError(
                "no PDF backend found. Install Ghostscript or run: pip install pymupdf"
            )
        compress_pymupdf(input_path, output_path, level)

    if verbose:
        backend = f"Ghostscript ({gs_exe})" if gs_exe else "PyMuPDF"
        in_size = _fmt_size(input_path)
        out_size = _fmt_size(output_path)
        in_bytes = os.path.getsize(input_path)
        out_bytes = os.path.getsize(output_path)
        reduction = (1 - out_bytes / in_bytes) * 100 if in_bytes > 0 else 0
        level_detail = PDFSETTINGS[level] if gs_exe else f"{DPI_TARGETS[level]} dpi"
        print(f"Backend: {backend}", file=sys.stderr)
        print(f"Level:   {level} ({level_detail})", file=sys.stderr)
        print(f"Input:   {input_path} ({in_size})", file=sys.stderr)
        print(f"Output:  {output_path} ({out_size})", file=sys.stderr)
        print(f"Reduced: {reduction:.1f}%", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Compress a PDF file using Ghostscript (if installed) or PyMuPDF as a fallback.",
        epilog=(
            "Examples:\n"
            "  python compress_pdf.py report.pdf report_small.pdf\n"
            "  python compress_pdf.py scan.pdf scan_print.pdf --level high --verbose"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="path to source PDF")
    parser.add_argument("output", help="path for compressed output PDF")
    parser.add_argument(
        "--level",
        choices=["low", "medium", "high"],
        default="medium",
        help="compression level: low (smallest), medium (default), high (best quality)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print backend, DPI target, and file sizes to stderr",
    )
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(input_path):
        print(f"Error: input path is not a file: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if not os.path.exists(output_dir):
        print(f"Error: output directory does not exist: {output_dir}", file=sys.stderr)
        sys.exit(1)

    if os.path.abspath(input_path) == os.path.abspath(output_path):
        print("Error: input and output paths must be different", file=sys.stderr)
        sys.exit(1)

    try:
        compress(input_path, output_path, args.level, args.verbose)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
