import base64
from email.message import EmailMessage
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/money-bill-saver/scripts"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mime = load("money_bill_saver_extract_mime", "extract_mime.py")
audit_check = load("money_bill_saver_audit_check_for_mime", "check_audit.py")


def pdf_bytes(text="SYNTHETIC STATEMENT total USD 1.62 for Jul 1 - Jul 6"):
    buffer = io.BytesIO()
    writer = canvas.Canvas(buffer)
    writer.drawString(40, 700, text)
    writer.showPage()
    writer.save()
    return buffer.getvalue()


def encrypted_pdf_bytes():
    reader = PdfReader(io.BytesIO(pdf_bytes()))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def synthetic_message(attachments=True, pdf=None):
    msg = EmailMessage()
    msg["From"] = "Billing <billing@example.test>"
    msg["To"] = "user@example.test"
    msg["Subject"] = "Synthetic statement"
    msg["Date"] = "Fri, 31 Jul 2026 10:00:00 +0000"
    msg.set_content("Your synthetic statement is attached.")
    msg.add_alternative("<html><body><p>Your <b>synthetic</b> statement</p><script>alert(1)</script></body></html>", subtype="html")
    if attachments:
        msg.add_attachment(pdf if pdf is not None else pdf_bytes(), maintype="application", subtype="pdf", filename="../../statement.pdf")
        big5 = "<html><body><table><tr><td>總計</td><td>271</td></tr></table></body></html>".encode("big5")
        msg.add_attachment(big5, maintype="text", subtype="html", filename="UC00000000.htm")
        msg.get_payload()[-1].set_param("charset", "big5")
        msg.add_attachment(b"\x89PNG\r\n\x1a\nfake", maintype="image", subtype="png", filename="receipt.png")
    return msg.as_bytes()


def gmail_raw_json(raw, message_id="18fsynthetic01", wrap=False):
    obj = {"id": message_id, "threadId": "18fsynthetic01", "internalDate": "1785492000000",
           "labelIds": ["INBOX"], "raw": base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")}
    return {"structuredContent": obj} if wrap else obj


class MimeExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def save(self, name, obj):
        path = self.base / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return path

    def test_gmail_raw_json_yields_attachments_hashes_and_text(self):
        raw = synthetic_message()
        src = self.save("msg.json", gmail_raw_json(raw))
        out = self.base / "out"
        manifest = mime.convert_files([src], out, extract_pdf=True)
        message = manifest["messages"][0]
        self.assertEqual(message["id"], "18fsynthetic01")
        self.assertEqual(message["subject"], "Synthetic statement")
        rows = {row["kind"]: row for row in message["attachments"]}
        self.assertEqual(set(rows), {"pdf", "html", "image"})
        pdf = rows["pdf"]
        self.assertEqual(pdf["status"], "extracted")
        saved = out / pdf["file"]
        self.assertTrue(saved.is_file())
        self.assertEqual(saved.parent, out / "18fsynthetic01" / "attachments")  # no path traversal
        self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(), pdf["sha256"])
        self.assertIn("USD 1.62", (out / pdf["text_file"]).read_text(encoding="utf-8"))
        html_text = (out / rows["html"]["text_file"]).read_text(encoding="utf-8")
        self.assertIn("總計", html_text)
        self.assertIn("271", html_text)
        self.assertTrue(rows["image"]["needs_visual_review"])
        body = (out / message["body_text_file"]).read_text(encoding="utf-8")
        self.assertIn("synthetic statement is attached", body)
        self.assertNotIn("alert(1)", body)
        self.assertEqual(oct(saved.stat().st_mode & 0o777), "0o600")

    def test_structured_content_wrapper_and_eml_are_accepted(self):
        raw = synthetic_message(attachments=False)
        wrapped = self.save("wrapped.json", gmail_raw_json(raw, "18fwrapped", wrap=True))
        eml = self.base / "message.eml"
        eml.write_bytes(raw)
        manifest = mime.convert_files([wrapped, eml], self.base / "out")
        ids = [m["id"] for m in manifest["messages"]]
        self.assertEqual(ids[0], "18fwrapped")
        self.assertEqual(len(ids[1]), 16)
        self.assertEqual(manifest["messages"][1]["attachments"], [])

    def test_payload_satisfies_audit_gate_mime_checks(self):
        src = self.save("msg.json", gmail_raw_json(synthetic_message()))
        out = self.base / "bundle" / "mail"
        manifest = mime.convert_files([src], out)
        message = manifest["messages"][0]
        saved = json.loads((out / message["message_file"]).read_text(encoding="utf-8"))
        payload = saved["payload"]
        self.assertTrue(audit_check._has_message_content(payload))
        self.assertEqual(audit_check._missing_text_parts(payload), [])
        required = {p["part_id"] for p in audit_check._meaningful_parts(payload)}
        offered = {s["part_id"] for s in message["evidence_sources"] if s["kind"] == "attachment"}
        self.assertTrue(required <= offered)

        bundle = self.base / "bundle"
        sources = []
        for entry in message["evidence_sources"]:
            entry = dict(entry, service_ids=["acme"], disposition="reviewed", note="Read synthetic content.")
            entry["file"] = f"mail/{entry['file']}"
            sources.append(entry)
        evidence = {"scope": {"mode": "files", "description": "One supplied synthetic statement message.", "as_of": "2026-09-16"},
                    "searches": [], "sources": sources}
        (bundle / "audit-evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
        report = {"subscriptions": [{"id": "acme", "name": "Acme", "status": "uncertain"}]}
        result = audit_check.assess(report, bundle / "audit-evidence.json")
        codes = {issue["code"] for issue in result["issues"]}
        self.assertFalse(codes & {"message_body_unverified", "untriaged_attachment", "invalid_attachment_parent"},
                         result["issues"])
        # Only the (intentionally absent) independent review may remain unresolved.
        self.assertFalse([i for i in result["issues"] if i["code"] == "inaccessible_evidence_file"
                          and not i["message"].startswith("independent_review_file")], result["issues"])

    def test_encrypted_and_fake_pdfs_are_flagged_not_extracted(self):
        src = self.save("enc.json", gmail_raw_json(synthetic_message(pdf=encrypted_pdf_bytes()), "18fenc"))
        fake = self.save("fake.json", gmail_raw_json(synthetic_message(pdf=b"not a pdf"), "18ffake"))
        manifest = mime.convert_files([src, fake], self.base / "out", extract_pdf=True)
        enc_pdf = next(a for a in manifest["messages"][0]["attachments"] if a["kind"] == "pdf")
        fake_pdf = next(a for a in manifest["messages"][1]["attachments"] if a["kind"] == "pdf")
        self.assertEqual(enc_pdf["status"], "pdf_unreadable")
        self.assertIn("password", enc_pdf["note"])
        self.assertTrue(enc_pdf["needs_visual_review"])
        self.assertEqual(fake_pdf["status"], "unexpected_content")

    def test_oversized_attachment_is_recorded_but_not_saved(self):
        src = self.save("msg.json", gmail_raw_json(synthetic_message()))
        manifest = mime.convert_files([src], self.base / "out", max_bytes=100)
        pdf = next(a for a in manifest["messages"][0]["attachments"] if a["kind"] == "pdf")
        self.assertEqual(pdf["status"], "skipped_too_large")
        self.assertIsNone(pdf["file"])
        entry = next(s for s in manifest["messages"][0]["evidence_sources"] if s.get("part_id") == pdf["part_id"])
        self.assertEqual(entry["disposition"], "inaccessible")

    def test_invalid_input_and_existing_output_are_refused(self):
        bad = self.save("bad.json", {"id": "x", "payload": {}})
        with self.assertRaises(mime.MimeError):
            mime.convert_files([bad], self.base / "out")
        src = self.save("msg.json", gmail_raw_json(synthetic_message(attachments=False)))
        out = self.base / "out2"
        mime.convert_files([src], out)
        with self.assertRaises(mime.MimeError):
            mime.convert_files([src], out)
        mime.convert_files([src], out, force=True)
        self.assertTrue((out / "manifest.json").is_file())

    def test_cli_prints_counts_only(self):
        src = self.save("msg.json", gmail_raw_json(synthetic_message()))
        proc = subprocess.run([sys.executable, str(SCRIPTS / "extract_mime.py"), str(src),
                               "--output-dir", str(self.base / "cli"), "--extract-pdf"],
                              capture_output=True, text=True, check=True)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["messages"], 1)
        self.assertEqual(summary["attachments"], 3)
        self.assertEqual(summary["pdf_extracted"], 1)
        self.assertNotIn("1.62", proc.stdout)


if __name__ == "__main__":
    unittest.main()
