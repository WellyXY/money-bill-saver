import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/money-bill-saver/scripts/extract_pdf.py"
spec = importlib.util.spec_from_file_location("subscription_extract_pdf", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def invoice(path, content="SYNTHETIC INVOICE: base 5.00, usage 30.00, allowance -5.00, tax 2.40"):
    writer = canvas.Canvas(str(path))
    writer.drawString(40, 700, content)
    writer.showPage()
    writer.save()


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_extract_preserves_amounts_pages_and_source_without_stdout_content(self):
        src = self.root / "invoice.pdf"
        invoice(src)
        before = hashlib.sha256(src.read_bytes()).hexdigest()
        out = self.root / "out"
        proc = subprocess.run([sys.executable, str(SCRIPT), str(src), "--output-dir", str(out)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("30.00", proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["pages"], 1)
        manifest = json.loads((out / "manifest.json").read_text())
        doc = manifest["documents"][0]
        text = Path(doc["text_file"]).read_text()
        self.assertIn("--- PAGE 1 ---", text)
        self.assertIn("allowance -5.00", text)
        self.assertEqual(doc["source_sha256"], before)
        self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(), before)
        self.assertFalse(doc["pages"][0]["needs_visual_review"])
        self.assertEqual(doc["pages"][0]["unexpected_control_character_count"], 0)
        self.assertEqual(doc["pages"][0]["unexpected_control_characters"], [])
        self.assertFalse(doc["pages"][0]["needs_field_cross_check"])
        self.assertEqual(doc["pages"][0]["review_reasons"], [])
        if os.name == "posix":
            self.assertEqual((out / "manifest.json").stat().st_mode & 0o777, 0o600)

    def test_control_characters_preserve_field_warning_without_forcing_page_render(self):
        src = self.root / "synthetic-controls.pdf"
        invoice(src)
        bad = "SYNTHETIC INVOICE ID DEMO\x000001; total 32.40\x00\x07\x7f\x85\x1f"
        normal = "SYNTHETIC INVOICE ID DEMO-0002\tamount 5.00\r\nordinary layout\f"
        out = self.root / "out"
        with patch.object(module, "extract_pages", return_value=([bad, normal], "synthetic", False)):
            result = module.extract_files([src], out)

        saved = json.loads((out / "manifest.json").read_text())
        self.assertEqual(saved, result)
        document = saved["documents"][0]
        pages = document["pages"]
        self.assertGreater(pages[0]["characters"], 30)
        self.assertFalse(pages[0]["needs_visual_review"])
        self.assertTrue(pages[0]["needs_field_cross_check"])
        self.assertEqual(pages[0]["review_reasons"], ["unexpected_control_characters"])
        self.assertEqual(pages[0]["unexpected_control_character_count"], 6)
        self.assertEqual(pages[0]["unexpected_control_characters"], [
            {"codepoint": "U+0000", "count": 2},
            {"codepoint": "U+0007", "count": 1},
            {"codepoint": "U+001F", "count": 1},
            {"codepoint": "U+007F", "count": 1},
            {"codepoint": "U+0085", "count": 1},
        ])
        self.assertFalse(pages[1]["needs_visual_review"])
        self.assertFalse(pages[1]["needs_field_cross_check"])
        self.assertEqual(pages[1]["unexpected_control_character_count"], 0)
        self.assertEqual(pages[1]["unexpected_control_characters"], [])
        expected = f"--- PAGE 1 ---\n{bad}\n\n--- PAGE 2 ---\n{normal}\n"
        self.assertEqual(Path(document["text_file"]).read_bytes(), expected.encode("utf-8"))

    def test_same_basename_different_sources_and_repeated_path(self):
        for d in ["one", "two"]:
            (self.root / d).mkdir()
            invoice(self.root / d / "invoice.pdf")
        a, b = self.root / "one/invoice.pdf", self.root / "two/invoice.pdf"
        result = module.extract_files([a, b, a], self.root / "out")
        self.assertEqual(len(result["documents"]), 2)
        self.assertNotEqual(result["documents"][0]["text_file"], result["documents"][1]["text_file"])

    def test_existing_outputs_preserved_then_explicitly_replaced(self):
        src = self.root / "invoice.pdf"
        invoice(src)
        out = self.root / "out"
        result = module.extract_files([src], out)
        text = Path(result["documents"][0]["text_file"])
        text.write_text("existing output")
        with self.assertRaises(module.ExtractionError):
            module.extract_files([src], out)
        self.assertEqual(text.read_text(), "existing output")
        module.extract_files([src], out, force=True)
        self.assertIn("SYNTHETIC INVOICE", text.read_text())

    def test_blank_page_needs_visual_review(self):
        src = self.root / "blank.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with src.open("wb") as stream:
            writer.write(stream)
        result = module.extract_files([src], self.root / "out")
        self.assertTrue(result["documents"][0]["pages"][0]["needs_visual_review"])

    def test_encrypted_and_invalid_inputs_leave_no_outputs(self):
        src = self.root / "locked.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt("test-password")
        with src.open("wb") as stream:
            writer.write(stream)
        out = self.root / "out"
        for item in [src, self.root / "absent.pdf"]:
            with self.assertRaises(module.ExtractionError):
                module.extract_files([item], out)
        self.assertFalse(out.exists())

    def test_poppler_fallback_preserves_empty_final_pdf_page(self):
        src = self.root / "invoice.pdf"
        invoice(src)
        response = subprocess.CompletedProcess([], 0, b"Invoice amount 32.40\f\f", b"")
        with patch.dict(sys.modules, {"pypdf": None}), patch.object(module.shutil, "which", return_value="/usr/bin/pdftotext"), patch.object(module.subprocess, "run", return_value=response) as run:
            pages, backend, warning = module.extract_pages(src)
        self.assertEqual(pages, ["Invoice amount 32.40", ""])
        self.assertEqual(backend, "pdftotext")
        self.assertFalse(warning)
        self.assertEqual(run.call_args.args[0][-2:], [str(src), "-"])

    def test_explicit_second_parser_preserves_signs_and_records_backend(self):
        src = self.root / "invoice.pdf"
        invoice(src)
        response = subprocess.CompletedProcess([], 0, b"Invoice amount 32.40, credit -5.00, id DEMO-0001\f", b"")
        with patch.object(module.shutil, "which", return_value="/usr/bin/pdftotext"), patch.object(module.subprocess, "run", return_value=response):
            result = module.extract_files([src], self.root / "alternative", backend="pdftotext")
        doc = result["documents"][0]
        self.assertEqual(doc["backend"], "pdftotext")
        self.assertIn("credit -5.00", Path(doc["text_file"]).read_text())
        self.assertEqual(doc["source_sha256"], hashlib.sha256(src.read_bytes()).hexdigest())

    def test_identical_bytes_reuse_extraction_but_keep_both_sources(self):
        src = self.root / "first.pdf"
        invoice(src)
        duplicate = self.root / "second.pdf"
        duplicate.write_bytes(src.read_bytes())
        with patch.object(module, "extract_pages", wraps=module.extract_pages) as parse:
            result = module.extract_files([src, duplicate], self.root / "out")
        self.assertEqual(parse.call_count, 1)
        a, b = result["documents"]
        self.assertEqual(a["source_sha256"], b["source_sha256"])
        self.assertNotEqual(a["source"], b["source"])
        self.assertNotEqual(a["text_file"], b["text_file"])
        self.assertFalse(a["extraction_reused"])
        self.assertTrue(b["extraction_reused"])

    def test_parser_and_decode_warnings_require_review_even_with_long_text(self):
        src = self.root / "invoice.pdf"
        invoice(src)
        text = "Invoice DEMO-0001 contains damaged text \ufffd, total 32.40"
        with patch.object(module, "extract_pages", return_value=([text], "synthetic", True)):
            result = module.extract_files([src], self.root / "out")
        page = result["documents"][0]["pages"][0]
        self.assertTrue(page["needs_visual_review"])
        self.assertEqual(page["review_reasons"], ["replacement_characters", "parser_warning"])

    def test_unavailable_explicit_parser_does_not_silently_switch_backend(self):
        src = self.root / "invoice.pdf"
        invoice(src)
        with patch.object(module.shutil, "which", return_value=None):
            with self.assertRaises(module.ExtractionError):
                module.extract_files([src], self.root / "out", backend="pdftotext")
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
