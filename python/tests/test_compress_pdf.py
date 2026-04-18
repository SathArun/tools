import io
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import compress_pdf  # noqa: E402


# ---------------------------------------------------------------------------
# detect_ghostscript()
# ---------------------------------------------------------------------------

class TestDetectGhostscript:
    def test_finds_gswin64c_on_path(self):
        with patch("shutil.which", side_effect=lambda n: "/usr/bin/gswin64c" if n == "gswin64c" else None):
            assert compress_pdf.detect_ghostscript() == "/usr/bin/gswin64c"

    def test_falls_back_to_gswin32c(self):
        def which(name):
            return "/usr/bin/gswin32c" if name == "gswin32c" else None
        with patch("shutil.which", side_effect=which):
            assert compress_pdf.detect_ghostscript() == "/usr/bin/gswin32c"

    def test_falls_back_to_gs(self):
        with patch("shutil.which", side_effect=lambda n: "/usr/bin/gs" if n == "gs" else None):
            assert compress_pdf.detect_ghostscript() == "/usr/bin/gs"

    def test_finds_via_program_files_glob(self):
        with patch("shutil.which", return_value=None), \
             patch("glob.glob", side_effect=lambda p: [r"C:\Program Files\gs\gs10.0\bin\gswin64c.exe"] if "gswin64c" in p else []):
            result = compress_pdf.detect_ghostscript()
        assert result == r"C:\Program Files\gs\gs10.0\bin\gswin64c.exe"

    def test_returns_none_when_nothing_found(self):
        with patch("shutil.which", return_value=None), \
             patch("glob.glob", return_value=[]):
            assert compress_pdf.detect_ghostscript() is None

    def test_prefers_which_over_glob(self):
        glob_called = []
        with patch("shutil.which", return_value="/usr/bin/gs"), \
             patch("glob.glob", side_effect=lambda p: glob_called.append(p) or []):
            result = compress_pdf.detect_ghostscript()
        assert result == "/usr/bin/gs"
        assert len(glob_called) == 0


# ---------------------------------------------------------------------------
# compress_ghostscript()
# ---------------------------------------------------------------------------

class TestCompressGhostscript:
    def _run_ok(self):
        return MagicMock(returncode=0, stderr="")

    def test_medium_uses_ebook_setting(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "medium", "/usr/bin/gs")
        cmd = mock_run.call_args[0][0]
        assert "-dPDFSETTINGS=/ebook" in cmd

    def test_low_uses_screen_setting(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "low", "/usr/bin/gs")
        cmd = mock_run.call_args[0][0]
        assert "-dPDFSETTINGS=/screen" in cmd

    def test_high_uses_printer_setting(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "high", "/usr/bin/gs")
        cmd = mock_run.call_args[0][0]
        assert "-dPDFSETTINGS=/printer" in cmd

    def test_uses_provided_executable(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "medium", "/custom/gs")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/custom/gs"

    def test_includes_input_and_output(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "medium", "gs")
        cmd = mock_run.call_args[0][0]
        assert "in.pdf" in cmd
        assert "-sOutputFile=out.pdf" in cmd

    def test_raises_runtime_error_on_nonzero_returncode(self):
        mock_result = MagicMock(returncode=1, stderr="bad input file")
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="bad input file"):
                compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "medium", "gs")

    def test_raises_with_generic_message_on_empty_stderr(self):
        mock_result = MagicMock(returncode=1, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Ghostscript failed"):
                compress_pdf.compress_ghostscript("in.pdf", "out.pdf", "medium", "gs")


# ---------------------------------------------------------------------------
# compress_pymupdf()
# ---------------------------------------------------------------------------

def _make_fitz_mock(images=None):
    """Build a minimal fitz mock. images is list of (xref, width, height, page_width_pts)."""
    fitz_mod = MagicMock()
    doc = MagicMock()
    fitz_mod.open.return_value = doc

    if not images:
        page = MagicMock()
        page.get_images.return_value = []
        page.rect.width = 612
        doc.__len__ = lambda self: 1
        doc.__getitem__ = lambda self, i: page
        return fitz_mod, doc, []

    pages = []
    page_mocks = []
    for xref, width, height, page_w in images:
        page = MagicMock()
        page.get_images.return_value = [(xref, None, None, None, None, None, None)]
        page.rect.width = page_w
        doc.extract_image.return_value = {
            "image": b"\xff\xd8\xff" + b"\x00" * 100,  # minimal JPEG-like bytes
            "width": width,
            "height": height,
            "ext": "jpeg",
        }
        page_mocks.append(page)

    doc.__len__ = lambda self: len(page_mocks)
    doc.__getitem__ = lambda self, i: page_mocks[i]
    return fitz_mod, doc, page_mocks


class TestCompressPymupdf:
    def test_saves_with_correct_flags(self):
        fitz_mock, doc, _ = _make_fitz_mock()
        pil_mock = MagicMock()
        with patch.dict(sys.modules, {"fitz": fitz_mock, "PIL": MagicMock(), "PIL.Image": pil_mock}):
            compress_pdf.compress_pymupdf("in.pdf", "out.pdf", "medium")
        doc.save.assert_called_once_with("out.pdf", garbage=4, deflate=True, clean=True)

    def test_skips_image_below_target_dpi(self):
        # Image at 72 dpi, target also 72 dpi (low) — should skip
        # page_width_pts=612, orig_width=612 → approx_dpi = (612/612)*72 = 72
        fitz_mock, doc, _ = _make_fitz_mock(images=[(1, 612, 792, 612)])
        pil_mock = MagicMock()
        with patch.dict(sys.modules, {"fitz": fitz_mock, "PIL": MagicMock(), "PIL.Image": pil_mock}):
            compress_pdf.compress_pymupdf("in.pdf", "out.pdf", "low")
        doc.update_stream.assert_not_called()

    def test_downsamples_high_dpi_image(self):
        # page_width_pts=612, orig_width=2448 → approx_dpi=(2448/612)*72=288
        # target for medium=150 → 150/288 < 1 so should downsample
        fitz_mock, doc, _ = _make_fitz_mock(images=[(2, 2448, 3264, 612)])
        pil_image = MagicMock()
        pil_image.resize.return_value = pil_image
        pil_image.convert.return_value = pil_image

        buf_mock = MagicMock()
        buf_mock.getvalue.return_value = b"compressed"

        pil_module = MagicMock()
        pil_module.Image.open.return_value = pil_image
        pil_module.Image.LANCZOS = 1

        with patch.dict(sys.modules, {"fitz": fitz_mock, "PIL": pil_module, "PIL.Image": pil_module.Image}), \
             patch("io.BytesIO", side_effect=[io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), io.BytesIO()]) as mock_bio:
            # We need the second BytesIO to behave like a buffer
            second_buf = io.BytesIO()
            mock_bio.side_effect = [io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), second_buf]
            compress_pdf.compress_pymupdf("in.pdf", "out.pdf", "medium")
        doc.update_stream.assert_called_once()

    def test_warning_on_bad_image_continues(self, capsys):
        fitz_mock, doc, _ = _make_fitz_mock(images=[(3, 2448, 3264, 612)])
        doc.extract_image.side_effect = Exception("corrupt image")
        with patch.dict(sys.modules, {"fitz": fitz_mock, "PIL": MagicMock(), "PIL.Image": MagicMock()}):
            compress_pdf.compress_pymupdf("in.pdf", "out.pdf", "medium")
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        doc.save.assert_called_once()

    def test_skips_duplicate_xrefs_across_pages(self):
        # Two pages referencing same xref=10 — should only process once
        fitz_mock = MagicMock()
        doc = MagicMock()
        fitz_mock.open.return_value = doc

        page0 = MagicMock()
        page0.get_images.return_value = [(10, None, None, None, None, None, None)]
        page0.rect.width = 612

        page1 = MagicMock()
        page1.get_images.return_value = [(10, None, None, None, None, None, None)]
        page1.rect.width = 612

        # High-DPI image so it would be downsampled if processed
        doc.extract_image.return_value = {
            "image": b"\x00" * 200,
            "width": 2448,
            "height": 3264,
            "ext": "jpeg",
        }
        doc.__len__ = lambda self: 2
        doc.__getitem__ = lambda self, i: [page0, page1][i]

        pil_image = MagicMock()
        pil_image.convert.return_value = pil_image
        pil_image.resize.return_value = pil_image
        pil_module = MagicMock()
        pil_module.Image.open.return_value = pil_image
        pil_module.Image.LANCZOS = 1

        with patch.dict(sys.modules, {"fitz": fitz_mock, "PIL": pil_module, "PIL.Image": pil_module.Image}):
            compress_pdf.compress_pymupdf("in.pdf", "out.pdf", "medium")

        # extract_image called only once despite two pages
        assert doc.extract_image.call_count == 1


# ---------------------------------------------------------------------------
# compress() dispatch
# ---------------------------------------------------------------------------

class TestCompressDispatch:
    def test_uses_ghostscript_when_detected(self):
        with patch("compress_pdf.detect_ghostscript", return_value="/usr/bin/gs"), \
             patch("compress_pdf.compress_ghostscript") as mock_gs, \
             patch("compress_pdf.compress_pymupdf") as mock_mu:
            compress_pdf.compress("in.pdf", "out.pdf", "medium", False)
        mock_gs.assert_called_once_with("in.pdf", "out.pdf", "medium", "/usr/bin/gs")
        mock_mu.assert_not_called()

    def test_falls_back_to_pymupdf_when_gs_absent(self):
        fitz_mock = MagicMock()
        with patch("compress_pdf.detect_ghostscript", return_value=None), \
             patch("compress_pdf.compress_pymupdf") as mock_mu, \
             patch.dict(sys.modules, {"fitz": fitz_mock}):
            compress_pdf.compress("in.pdf", "out.pdf", "medium", False)
        mock_mu.assert_called_once()

    def test_falls_back_to_pymupdf_on_gs_file_not_found(self):
        with patch("compress_pdf.detect_ghostscript", return_value="/bad/path/gs"), \
             patch("compress_pdf.compress_ghostscript", side_effect=FileNotFoundError), \
             patch("compress_pdf.compress_pymupdf") as mock_mu, \
             patch.dict(sys.modules, {"fitz": MagicMock()}):
            compress_pdf.compress("in.pdf", "out.pdf", "medium", False)
        mock_mu.assert_called_once()

    def test_raises_import_error_when_no_backend(self):
        broken_modules = {k: v for k, v in sys.modules.items()}
        broken_modules.pop("fitz", None)
        with patch("compress_pdf.detect_ghostscript", return_value=None), \
             patch.dict(sys.modules, {"fitz": None}):
            with pytest.raises(ImportError, match="pip install pymupdf"):
                compress_pdf.compress("in.pdf", "out.pdf", "medium", False)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain:
    def _valid_fs(self, input_exists=True, input_is_file=True, output_dir_exists=True):
        def side_exists(path):
            if path == "in.pdf":
                return input_exists
            return output_dir_exists
        def side_isfile(path):
            return input_is_file
        return side_exists, side_isfile

    def test_success_exits_0(self):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress"):
            compress_pdf.main()  # should not raise SystemExit

    def test_input_not_found_exits_1(self, capsys):
        with patch("sys.argv", ["compress_pdf.py", "missing.pdf", "out.pdf"]), \
             patch("os.path.exists", return_value=False), \
             pytest.raises(SystemExit) as exc:
            compress_pdf.main()
        assert exc.value.code == 1
        assert "not found" in capsys.readouterr().err

    def test_input_is_directory_exits_1(self, capsys):
        with patch("sys.argv", ["compress_pdf.py", "mydir", "out.pdf"]), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.isfile", return_value=False), \
             pytest.raises(SystemExit) as exc:
            compress_pdf.main()
        assert exc.value.code == 1
        assert "not a file" in capsys.readouterr().err

    def test_output_dir_missing_exits_1(self, capsys):
        def fake_exists(p):
            return p == "in.pdf"
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "/no/such/dir/out.pdf"]), \
             patch("os.path.exists", side_effect=fake_exists), \
             patch("os.path.isfile", return_value=True), \
             pytest.raises(SystemExit) as exc:
            compress_pdf.main()
        assert exc.value.code == 1
        assert "directory does not exist" in capsys.readouterr().err

    def test_same_input_output_exits_1(self, capsys):
        with patch("sys.argv", ["compress_pdf.py", "same.pdf", "same.pdf"]), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.abspath", return_value="/abs/same.pdf"), \
             pytest.raises(SystemExit) as exc:
            compress_pdf.main()
        assert exc.value.code == 1
        assert "must be different" in capsys.readouterr().err

    def test_no_backend_exits_1(self, capsys):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress", side_effect=ImportError("no PDF backend found. Install Ghostscript or run: pip install pymupdf")), \
             pytest.raises(SystemExit) as exc:
            compress_pdf.main()
        assert exc.value.code == 1
        assert "pip install pymupdf" in capsys.readouterr().err

    def test_runtime_error_exits_1(self, capsys):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress", side_effect=RuntimeError("gs failed")), \
             pytest.raises(SystemExit) as exc:
            compress_pdf.main()
        assert exc.value.code == 1
        assert "gs failed" in capsys.readouterr().err

    def test_default_level_is_medium(self):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress") as mock_compress:
            compress_pdf.main()
        assert mock_compress.call_args[0][2] == "medium"

    def test_level_low_passed_through(self):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf", "--level", "low"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress") as mock_compress:
            compress_pdf.main()
        assert mock_compress.call_args[0][2] == "low"

    def test_level_high_passed_through(self):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf", "--level", "high"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress") as mock_compress:
            compress_pdf.main()
        assert mock_compress.call_args[0][2] == "high"

    def test_verbose_flag_passed_through(self):
        side_exists, side_isfile = self._valid_fs()
        with patch("sys.argv", ["compress_pdf.py", "in.pdf", "out.pdf", "--verbose"]), \
             patch("os.path.exists", side_effect=side_exists), \
             patch("os.path.isfile", side_effect=side_isfile), \
             patch("os.path.abspath", side_effect=lambda p: p), \
             patch("compress_pdf.compress") as mock_compress:
            compress_pdf.main()
        assert mock_compress.call_args[0][3] is True
