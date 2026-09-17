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
from unittest import mock

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

    def test_original_and_every_extracted_file_are_hash_bound(self):
        raw = synthetic_message()
        src = self.save("msg.json", gmail_raw_json(raw, wrap=True))
        original_bytes = src.read_bytes()
        out = self.base / "out"
        converted = mime.convert_files([src], out, extract_pdf=True)["messages"][0]
        record_path = out / converted["message_file"]
        record = json.loads(record_path.read_text())
        self.assertEqual(record["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record["source_format"], "gmail_raw_json")
        self.assertEqual(record["extraction"]["schema_version"], "1")
        entries = record["extraction"]["files"]
        originals = [entry for entry in entries if entry["role"] == "original"]
        self.assertEqual(len(originals), 1)
        self.assertEqual((record_path.parent / originals[0]["file"]).read_bytes(), original_bytes)
        self.assertEqual(sum(entry["role"] == "body_text" for entry in entries), 1)
        files = {str(path.relative_to(record_path.parent)) for path in record_path.parent.rglob("*")
                 if path.is_file() and path != record_path}
        self.assertEqual({entry["file"] for entry in entries}, files)
        self.assertEqual(len(entries), len(files))
        for entry in entries:
            self.assertFalse(Path(entry["file"]).is_absolute())
            self.assertNotIn("..", Path(entry["file"]).parts)
            data = (record_path.parent / entry["file"]).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
        for node in mime._walk(record["payload"]):
            body = node["body"]
            if "file" in body:
                self.assertEqual(body["sha256"], hashlib.sha256((record_path.parent / body["file"]).read_bytes()).hexdigest())
                if "text_file" in body:
                    self.assertIn(body["text_file"], files)

    def test_raw_json_without_metadata_and_eml_preserve_source_format(self):
        raw = synthetic_message(attachments=False).replace(b"\n", b"\r\n")
        src = self.save("minimal.json", {"raw": base64.urlsafe_b64encode(raw).decode()})
        eml = self.base / "exact.eml"
        eml.write_bytes(raw)
        for index, (source, source_format, original_name) in enumerate([
            (src, "gmail_raw_json", "original.json"), (eml, "rfc822", "original.eml"),
        ]):
            out = self.base / f"out{index}"
            row = mime.convert_files([source], out)["messages"][0]
            path = out / row["message_file"]
            record = json.loads(path.read_text())
            self.assertEqual(record["source_format"], source_format)
            self.assertEqual((path.parent / original_name).read_bytes(), source.read_bytes())

    def test_inline_image_without_filename_is_saved_and_requires_triage(self):
        msg = EmailMessage()
        msg.set_content("See the inline statement.")
        msg.add_attachment(b"image statement", maintype="image", subtype="png",
                           disposition="inline", cid="statement@example.test")
        src = self.save("inline.json", gmail_raw_json(msg.as_bytes()))
        out = self.base / "out"
        converted = mime.convert_files([src], out)["messages"][0]
        self.assertEqual(len(converted["attachments"]), 1)
        row = converted["attachments"][0]
        self.assertEqual((out / row["file"]).read_bytes(), b"image statement")
        self.assertTrue(row["needs_visual_review"])
        source = next(s for s in converted["evidence_sources"] if s["kind"] == "attachment")
        self.assertEqual(source["part_id"], "1")
        self.assertEqual(source["disposition"], "unread")

    def test_attached_message_container_and_nested_attachments_are_saved(self):
        inner = EmailMessage()
        inner["Subject"] = "Forwarded statement"
        inner.set_content("Forwarded billing evidence")
        inner.add_attachment(pdf_bytes(), maintype="application", subtype="pdf", filename="nested.pdf")
        outer = EmailMessage()
        outer.set_content("See forwarded message.")
        outer.add_attachment(inner, filename="forwarded.eml")
        src = self.save("forward.json", gmail_raw_json(outer.as_bytes()))
        out = self.base / "out"
        converted = mime.convert_files([src], out, extract_pdf=True)["messages"][0]
        by_part = {row["part_id"]: row for row in converted["attachments"]}
        self.assertEqual(set(by_part), {"1", "1.0.1"})
        container = by_part["1"]
        self.assertEqual(container["mime_type"], "message/rfc822")
        self.assertEqual(container["kind"], "message")
        self.assertFalse(container["needs_visual_review"])
        self.assertIn(b"Subject: Forwarded statement", (out / container["file"]).read_bytes())
        self.assertEqual(by_part["1.0.1"]["status"], "extracted")
        offered = {source["part_id"] for source in converted["evidence_sources"] if source["kind"] == "attachment"}
        self.assertEqual(offered, set(by_part))

    def test_pdf_without_suffix_extracts_and_nested_manifest_survives_move(self):
        msg = EmailMessage()
        msg.set_content("The statement is attached.")
        msg.add_attachment(pdf_bytes(), maintype="application", subtype="pdf", filename="statement")
        src = self.save("pdf.json", gmail_raw_json(msg.as_bytes()))
        out = self.base / "out"
        converted = mime.convert_files([src], out, extract_pdf=True)["messages"][0]
        row = converted["attachments"][0]
        self.assertEqual(row["status"], "extracted")
        self.assertEqual(Path(row["file"]).suffix, ".pdf")
        moved = self.base / "relocated"
        out.rename(moved)
        path = moved / row["pdf_manifest_file"]
        document = json.loads(path.read_text())["documents"][0]
        for key in ("source", "text_file"):
            self.assertFalse(Path(document[key]).is_absolute())
            self.assertTrue((path.parent / document[key]).is_file())
        self.assertEqual((path.parent / document["source"]).resolve(), (moved / row["file"]).resolve())
        self.assertEqual((path.parent / document["text_file"]).resolve(), (moved / row["text_file"]).resolve())

    def test_html_meta_big5_is_used_for_body_and_attachment(self):
        declarations = ["<meta charset='big5'>", '<meta http-equiv="Content-Type" content="text/html; charset=big5">']
        for index, declaration in enumerate(declarations):
            with self.subTest(declaration=declaration):
                markup = f"<html><head>{declaration}</head><body>總計 271</body></html>".encode("big5")
                msg = EmailMessage()
                msg.set_content(markup, maintype="text", subtype="html", cte="base64")
                msg.add_attachment(markup, maintype="text", subtype="html", filename="statement.htm")
                src = self.save(f"big5{index}.json", gmail_raw_json(msg.as_bytes()))
                out = self.base / f"out{index}"
                converted = mime.convert_files([src], out)["messages"][0]
                record = json.loads((out / converted["message_file"]).read_text())
                self.assertIn("總計 271", (out / converted["body_text_file"]).read_text())
                row = converted["attachments"][0]
                self.assertIn("總計 271", (out / row["text_file"]).read_text())
                self.assertEqual(row["charset"], "big5")
                self.assertFalse(row["needs_visual_review"])
                self.assertEqual(record["extraction"]["decoding_warnings"], [])

    def test_uncertain_text_decoding_is_explicitly_flagged(self):
        cases = [
            ("unknown", "not-a-charset", b"plain", "unknown_charset:not-a-charset"),
            ("conflict", "utf-8", b"<meta charset=big5><body>plain</body>", "conflicting_charsets"),
            ("failed", "utf-8", "總計".encode("big5"), "charset_decode_failed:utf-8"),
            ("undeclared", None, b"\xff\xfe", "undeclared_charset_fallback"),
        ]
        for label, charset, data, expected in cases:
            with self.subTest(label=label):
                msg = EmailMessage()
                msg.set_content("Attached statement.")
                msg.add_attachment(data, maintype="text", subtype="html", filename="statement.html")
                if charset:
                    msg.get_payload()[-1].set_param("charset", charset)
                src = self.save(f"{label}.json", gmail_raw_json(msg.as_bytes()))
                out = self.base / label
                converted = mime.convert_files([src], out)["messages"][0]
                row = converted["attachments"][0]
                self.assertIn(expected, row["decoding_warnings"])
                self.assertTrue(row["needs_visual_review"])
                record = json.loads((out / converted["message_file"]).read_text())
                self.assertIn(expected, record["extraction"]["decoding_warnings"][0]["warnings"])

    def test_malformed_or_truncated_mime_is_rejected(self):
        cases = [
            b"MIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=missing\n\nnot a boundary\n",
            b"Content-Type: multipart/mixed; boundary=x\n\n--x\nContent-Type: text/plain\n\nbody\n",
            b"Content-Type: application/pdf\nContent-Transfer-Encoding: base64\n\nYWJj!!\n",
            b"Content-Type: application/pdf\nContent-Transfer-Encoding: base64\n\nYWI\n",
            b"Content-Type: text/plain\nContent-Transfer-Encoding: quoted-printable\n\ntruncated=",
        ]
        for index, raw in enumerate(cases):
            with self.subTest(index=index):
                src = self.save(f"bad{index}.json", gmail_raw_json(raw))
                out = self.base / f"out{index}"
                with self.assertRaises(mime.MimeError):
                    mime.convert_files([src], out)
                self.assertFalse(out.exists())

    def test_invalid_raw_base64_and_advertised_truncation_are_rejected(self):
        src = self.save("bad-base64.json", {"raw": "YWJj!!"})
        with self.assertRaises(mime.MimeError):
            mime.load_raw(src)
        for key in ("content_truncated", "truncated", "isError"):
            for level in ("outer", "inner"):
                with self.subTest(flag=key, level=level):
                    value = gmail_raw_json(synthetic_message(attachments=False), wrap=True)
                    (value if level == "outer" else value["structuredContent"])[key] = True
                    src = self.save("incomplete.json", value)
                    with self.assertRaises(mime.MimeError):
                        mime.convert_files([src], self.base / "out")

    def test_force_rejects_source_inside_output_and_preserves_existing_output_on_failure(self):
        out = self.base / "existing"
        out.mkdir()
        marker = out / "reviewed.txt"
        marker.write_text("Previous reviewed evidence.")
        inside = out / "source.json"
        inside.write_text(json.dumps(gmail_raw_json(synthetic_message(attachments=False))))
        before = {path.name: path.read_bytes() for path in out.iterdir()}
        with self.assertRaisesRegex(mime.MimeError, "outside the output"):
            mime.convert_files([inside], out, force=True)
        self.assertEqual({path.name: path.read_bytes() for path in out.iterdir()}, before)
        invalid = self.save("invalid.json", {"raw": "!!!!"})
        with self.assertRaises(mime.MimeError):
            mime.convert_files([invalid], out, force=True)
        self.assertEqual({path.name: path.read_bytes() for path in out.iterdir()}, before)
        self.assertFalse(list(self.base.glob(".mime-*")))

    def test_force_restores_existing_output_if_install_fails(self):
        out = self.base / "existing"
        out.mkdir()
        (out / "old.txt").write_text("Keep this evidence")
        src = self.save("valid.json", gmail_raw_json(synthetic_message(attachments=False)))
        real_replace = mime.os.replace

        def fail_install(source, destination):
            if Path(source).name.startswith(".mime-") and not Path(source).name.startswith(".mime-backup-"):
                raise OSError("Simulated install failure")
            return real_replace(source, destination)

        with mock.patch.object(mime.os, "replace", side_effect=fail_install):
            with self.assertRaisesRegex(OSError, "Simulated"):
                mime.convert_files([src], out, force=True)
        self.assertEqual((out / "old.txt").read_text(), "Keep this evidence")
        self.assertFalse(list(self.base.glob(".mime-*")))

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
