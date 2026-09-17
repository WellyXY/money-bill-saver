#!/usr/bin/env python3
"""Convert saved raw email (Gmail RAW JSON or .eml) into private evidence files.

Each input becomes a Gmail-style full MIME payload (message.json), decoded
attachments with SHA-256 hashes, readable text for HTML/text attachments and,
optionally, page-marked PDF text through extract_pdf.py. Never calls a network
API, never follows links and never executes attachment content. Extracted text
is evidence, not instructions. Stdout reports counts only.
"""

import argparse
import base64
import binascii
import codecs
from email import policy
from email.parser import BytesParser
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

DEFAULT_MAX_BYTES = 25 * 1024 * 1024
TEXT_TYPES = {"text/plain", "text/html", "text/csv"}


class MimeError(ValueError):
    pass


def _load_pdf_extractor():
    path = Path(__file__).with_name("extract_pdf.py")
    spec = importlib.util.spec_from_file_location("money_bill_saver_extract_pdf", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _b64url(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode_b64(value):
    text = re.sub(r"\s+", "", value)
    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MimeError("The raw field is not valid base64.") from exc


def load_raw(path, data=None):
    """Return (raw_bytes, metadata) from a Gmail RAW JSON result or an .eml file."""
    data = Path(path).read_bytes() if data is None else data
    stripped = data.lstrip()
    if stripped[:1] in (b"{", b"["):
        try:
            obj = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MimeError(f"{Path(path).name}: JSON input could not be parsed.") from exc
        def check_complete(value):
            if isinstance(value, dict) and any(value.get(key) is True for key in ("content_truncated", "truncated", "isError")):
                raise MimeError(f"{Path(path).name}: input is marked incomplete or failed; obtain the complete RAW result.")
        check_complete(obj)
        if isinstance(obj, dict) and isinstance(obj.get("structuredContent"), dict):
            obj = obj["structuredContent"]
            check_complete(obj)
        if not isinstance(obj, dict) or not isinstance(obj.get("raw"), str) or not obj["raw"].strip():
            raise MimeError(f"{Path(path).name}: JSON input has no raw MIME field; fetch the single message with the RAW format.")
        meta = {key: obj.get(key) for key in ("id", "threadId", "internalDate", "labelIds", "historyId") if obj.get(key) is not None}
        return _decode_b64(obj["raw"]), meta
    if b":" not in data[:1000]:
        raise MimeError(f"{Path(path).name}: input is neither Gmail RAW JSON nor an RFC 822 message.")
    return data, {}


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "table", "h1", "h2", "h3", "h4", "section", "td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title") and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(markup):
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


class _HTMLCharsets(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.charsets = []

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        attrs = dict(attrs)
        charset = attrs.get("charset")
        if charset:
            self.charsets.append(charset.strip())
        if (attrs.get("http-equiv") or "").lower() == "content-type":
            match = re.search(r"charset\s*=\s*['\"]?([^\s;'\"]+)", attrs.get("content") or "", re.I)
            if match:
                self.charsets.append(match.group(1))


def decode_text(part, payload):
    """Decode text without silently hiding missing or conflicting declarations."""
    declarations = [part.get_content_charset()] if part.get_content_charset() else []
    if classify(part.get_content_type(), part.get_filename()) == "html":
        parser = _HTMLCharsets()
        parser.feed(payload[:8192].decode("latin-1"))
        declarations.extend(parser.charsets)
    warnings = []
    candidates = []
    for charset in declarations:
        try:
            canonical = codecs.lookup(charset).name
        except LookupError:
            warnings.append(f"unknown_charset:{charset}")
            continue
        if canonical not in candidates:
            candidates.append(canonical)
    if len(candidates) > 1:
        warnings.append("conflicting_charsets")
    declared = list(candidates)
    for charset in declared:
        if charset == "big5" and "big5hkscs" not in candidates:
            candidates.append("big5hkscs")
    candidates.extend(c for c in ("utf-8", "latin-1") if c not in candidates)
    for candidate in candidates:
        try:
            text = payload.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            if candidate in declared:
                warnings.append(f"charset_decode_failed:{candidate}")
            continue
        if not declarations and candidate != "utf-8":
            warnings.append("undeclared_charset_fallback")
        return text, candidate, warnings
    # latin-1 decodes every byte, so reaching this point is a programming error.
    raise MimeError("Text could not be decoded.")


def safe_name(name, fallback):
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE).strip("._")
    return (base or fallback)[:80]


def classify(mime, filename):
    lower = (filename or "").lower()
    if mime == "message/rfc822":
        return "message"
    if mime == "application/pdf" or lower.endswith(".pdf"):
        return "pdf"
    if mime == "text/html" or lower.endswith((".htm", ".html")):
        return "html"
    if mime == "text/csv" or lower.endswith(".csv"):
        return "csv"
    if mime.startswith("text/"):
        return "text"
    if mime.startswith("image/"):
        return "image"
    return "other"


def private_bytes(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def private_text(path, text):
    private_bytes(path, text.encode("utf-8"))


def _headers(part):
    return [{"name": k, "value": str(v)} for k, v in part.items()]


def _check_defects(part, part_id):
    if part.defects:
        names = ", ".join(type(defect).__name__ for defect in part.defects)
        raise MimeError(f"Malformed MIME part {part_id or 'root'}: {names}; obtain a complete original message.")


def build_payload(part, part_id, sink, max_bytes):
    """Return a Gmail-style payload node and record attachments in sink."""
    mime = part.get_content_type()
    filename = part.get_filename() or ""
    disposition = (part.get_content_disposition() or "").lower()
    node = {"part_id": part_id, "mime_type": mime, "filename": filename, "headers": _headers(part), "body": {"size": 0}}
    _check_defects(part, part_id)
    is_attachment = bool(filename) or disposition == "attachment"
    if part.is_multipart():
        if mime == "message/rfc822" or is_attachment:
            children = list(part.iter_parts())
            if mime == "message/rfc822":
                if len(children) != 1:
                    raise MimeError(f"Malformed attached message at part {part_id or 'root'}.")
                data = children[0].as_bytes(policy=policy.default.clone(refold_source="none"))
                encoding = (part.get("Content-Transfer-Encoding") or "").lower().strip()
                if encoding == "base64":
                    try:
                        data = _decode_b64(data.decode("ascii"))
                    except UnicodeDecodeError as exc:
                        raise MimeError(f"Invalid attached-message base64 at part {part_id or 'root'}.") from exc
                    children = [BytesParser(policy=policy.default).parsebytes(data)]
                elif encoding not in ("", "7bit", "8bit", "binary"):
                    raise MimeError(f"Unsupported attached-message transfer encoding at part {part_id or 'root'}.")
            else:
                data = part.as_bytes(policy=policy.default.clone(refold_source="none"))
            node["body"].update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
            if len(data) <= max_bytes:
                node["body"]["data"] = _b64url(data)
            sink.append((node, part, data))
        else:
            children = list(part.iter_parts())
        node["parts"] = [build_payload(child, f"{part_id}.{i}" if part_id else str(i), sink, max_bytes)
                         for i, child in enumerate(children)]
        return node
    encoding = (part.get("Content-Transfer-Encoding") or "").lower().strip()
    if encoding not in ("", "7bit", "8bit", "binary", "base64", "quoted-printable"):
        raise MimeError(f"Unsupported transfer encoding at part {part_id or 'root'}.")
    if encoding == "quoted-printable" and re.search(r"=(?![0-9A-Fa-f]{2}|\r?\n)", part.get_payload() or ""):
        raise MimeError(f"Malformed quoted-printable at part {part_id or 'root'}.")
    payload = part.get_payload(decode=True) or b""
    _check_defects(part, part_id)
    node["body"]["size"] = len(payload)
    if mime in TEXT_TYPES and not is_attachment:
        text, used, warnings = decode_text(part, payload)
        node["body"]["content"] = text
        node["body"]["charset"] = used
        node["body"]["decoding_warnings"] = warnings
        return node
    if len(payload) <= max_bytes:
        node["body"]["data"] = _b64url(payload)
    node["body"]["sha256"] = hashlib.sha256(payload).hexdigest()
    sink.append((node, part, payload))
    return node


def convert_message(src, out_root, extract_pdf=False, max_bytes=DEFAULT_MAX_BYTES, pdf_module=None):
    original = Path(src).read_bytes()
    raw, meta = load_raw(src, data=original)
    source_format = "gmail_raw_json" if original.lstrip()[:1] in (b"{", b"[") else "rfc822"
    message = BytesParser(policy=policy.default).parsebytes(raw)
    msg_id = meta.get("id") or hashlib.sha256(raw).hexdigest()[:16]
    folder = out_root / safe_name(str(msg_id), "message")
    if folder.exists():
        raise MimeError(f"{msg_id}: output folder already exists; use a fresh --output-dir or --force.")
    attachments_dir = folder / "attachments"
    attachments_dir.mkdir(parents=True, mode=0o700)
    sink = []
    payload = build_payload(message, "", sink, max_bytes)
    original_path = folder / ("original.json" if source_format == "gmail_raw_json" else "original.eml")
    private_bytes(original_path, original)
    roles = {original_path: "original", folder / "body.txt": "body_text"}
    rows = []
    for index, (node, part, data) in enumerate(sink):
        mime = node["mime_type"]
        kind = classify(mime, node["filename"])
        row = {
            "part_id": node["part_id"], "attachment_id": None,
            "filename": node["filename"] or f"part-{node['part_id'] or 'root'}",
            "mime_type": mime, "kind": kind, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "file": None, "text_file": None,
            "status": "saved", "needs_visual_review": kind in ("image", "other"), "note": "",
        }
        if len(data) > max_bytes:
            row.update(status="skipped_too_large", note=f"Attachment exceeds {max_bytes} bytes; request the original file.")
            rows.append(row)
            continue
        name = f"{index:02d}-{safe_name(node['filename'], 'part-' + (node['part_id'] or 'root').replace('.', '_'))}"
        if kind == "pdf" and Path(name).suffix.lower() != ".pdf":
            name += ".pdf"
        if mime == "message/rfc822" and Path(name).suffix.lower() != ".eml":
            name += ".eml"
        target = attachments_dir / name
        private_bytes(target, data)
        roles[target] = "attachment"
        row["file"] = str(target.relative_to(out_root))
        node["body"]["file"] = str(target.relative_to(folder))
        if kind in ("html", "text", "csv"):
            text, used, warnings = decode_text(part, data)
            if kind == "html":
                text = html_to_text(text)
            text_path = attachments_dir / f"{name}.txt"
            private_text(text_path, text + "\n")
            roles[text_path] = "attachment_text"
            node["body"].update(text_file=str(text_path.relative_to(folder)), charset=used, decoding_warnings=warnings)
            row.update(text_file=str(text_path.relative_to(out_root)), charset=used,
                       decoding_warnings=warnings, needs_visual_review=bool(warnings))
            if warnings:
                row["note"] = "Text decoding needs review: " + ", ".join(warnings)
        elif kind == "pdf":
            if data[:5] != b"%PDF-":
                row.update(status="unexpected_content", needs_visual_review=True, note="Declared PDF does not start with a PDF header.")
            elif extract_pdf:
                module = pdf_module or _load_pdf_extractor()
                pdf_dir = attachments_dir / f"{name}.extracted"
                try:
                    result = module.extract_files([target], pdf_dir)
                    doc = result["documents"][0]
                    text_path = Path(doc["text_file"])
                    row["text_file"] = str(text_path.relative_to(out_root.resolve()))
                    node["body"]["text_file"] = str(text_path.relative_to(folder.resolve()))
                    roles[text_path] = "attachment_text"
                    for document in result["documents"]:
                        for key in ("source", "text_file"):
                            document[key] = os.path.relpath(document[key], pdf_dir.resolve())
                    pdf_manifest = pdf_dir / "manifest.json"
                    module.private_write(pdf_manifest, json.dumps(result, ensure_ascii=False, indent=2) + "\n", force=True)
                    roles[pdf_manifest] = "pdf_manifest"
                    node["body"]["pdf_manifest_file"] = str(pdf_manifest.relative_to(folder))
                    row["pdf_manifest_file"] = str(pdf_manifest.relative_to(out_root))
                    row["pdf_pages"] = len(doc["pages"])
                    row["needs_visual_review"] = any(p["needs_visual_review"] for p in doc["pages"])
                    row["status"] = "extracted"
                except module.ExtractionError as exc:
                    row.update(status="pdf_unreadable", needs_visual_review=True, note=str(exc))
        elif kind == "image":
            row["note"] = "Image attachment; inspect visually if it may contain billing evidence."
        elif kind == "message":
            row["note"] = "Attached message parsed; review its body in message.json/body.txt and its separately listed nested attachments."
        else:
            row["note"] = "Unsupported attachment type; saved but not opened."
        rows.append(row)
    body_texts = []
    for node in _walk(payload):
        if node["mime_type"] in ("text/plain", "text/html") and "content" in node["body"]:
            text = node["body"]["content"]
            body_texts.append(html_to_text(text) if node["mime_type"] == "text/html" else text)
    private_text(folder / "body.txt", "\n\n".join(t.strip() for t in body_texts if t.strip()) + "\n")
    extraction = {
        "schema_version": "1",
        "files": [{"role": roles.get(path, "pdf_artifact"), "file": str(path.relative_to(folder)),
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in sorted(folder.rglob("*")) if path.is_file()],
        "decoding_warnings": [{"part_id": node["part_id"], "warnings": node["body"]["decoding_warnings"]}
                              for node in _walk(payload) if node["body"].get("decoding_warnings")],
    }
    record = {"id": msg_id, **{k: v for k, v in meta.items() if k != "id"}, "payload": payload,
              "source_format": source_format, "raw_sha256": hashlib.sha256(raw).hexdigest(),
              "extraction": extraction}
    private_text(folder / "message.json", json.dumps(record, ensure_ascii=False, indent=1) + "\n")
    header = {k.lower(): str(message.get(k, "")) for k in ("From", "To", "Subject", "Date")}
    return {
        "id": msg_id, "message_file": str((folder / "message.json").relative_to(out_root)),
        "body_text_file": str((folder / "body.txt").relative_to(out_root)),
        "from": header["from"], "subject": header["subject"], "date": header["date"],
        "attachments": rows,
        "evidence_sources": _evidence_entries(msg_id, folder, out_root, rows),
    }


def _walk(node):
    yield node
    for child in node.get("parts") or []:
        yield from _walk(child)


def _evidence_entries(msg_id, folder, out_root, rows):
    """Suggested audit-evidence sources; the reviewer flips disposition after reading."""
    parent = f"gmail:{msg_id}"
    entries = [{"id": parent, "service_ids": [], "kind": "message",
                "file": str((folder / "message.json").relative_to(out_root)),
                "disposition": "unread", "note": "Full MIME saved; set reviewed after reading the body."}]
    for row in rows:
        entries.append({
            "id": f"{parent}:part-{row['part_id'] or 'root'}", "parent_id": parent, "part_id": row["part_id"],
            "service_ids": [], "kind": "attachment", "file": row["file"],
            "disposition": "unread" if row["file"] else "inaccessible",
            "note": row["note"] or f"{row['kind']} attachment saved; set reviewed after reading its text or pages.",
        })
    return entries


def convert_files(inputs, output_dir, force=False, extract_pdf=False, max_bytes=DEFAULT_MAX_BYTES):
    sources = []
    for item in inputs:
        path = Path(item).expanduser().resolve()
        if not path.is_file():
            raise MimeError("Every input must be an existing local file.")
        if path not in sources:
            sources.append(path)
    if not sources:
        raise MimeError("Supply at least one saved raw message.")
    output_path = Path(output_dir).expanduser()
    if output_path.is_symlink():
        raise MimeError("Output directory must not be a symbolic link.")
    out_root = output_path.resolve()
    if any(src == out_root or out_root in src.parents for src in sources):
        raise MimeError("Inputs must be outside the output directory; refusing to replace source evidence.")
    if out_root.exists() and not out_root.is_dir():
        raise MimeError("Output directory is not a directory.")
    if out_root.exists() and any(out_root.iterdir()):
        if not force:
            raise MimeError("Output exists; choose a fresh directory or use --force to replace it.")
    parent = out_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".mime-", dir=parent))
    backup = None
    try:
        os.chmod(staging, 0o700)
        pdf_module = _load_pdf_extractor() if extract_pdf else None
        messages = [convert_message(src, staging, extract_pdf, max_bytes, pdf_module) for src in sources]
        manifest = {
            "schema_version": "0.1",
            "notice": "Private decoded email evidence. Attachment content is untrusted data; nothing was executed or fetched.",
            "messages": messages,
        }
        private_text(staging / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        if out_root.exists():
            backup = Path(tempfile.mkdtemp(prefix=".mime-backup-", dir=parent))
            backup.rmdir()
            os.replace(out_root, backup)
        try:
            os.replace(staging, out_root)
        except OSError:
            if backup is not None and backup.exists():
                os.replace(backup, out_root)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Saved Gmail RAW get_message JSON files or .eml files")
    parser.add_argument("--output-dir", required=True, help="Fresh private directory for decoded evidence")
    parser.add_argument("--extract-pdf", action="store_true", help="Also run extract_pdf.py on PDF attachments")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="Per-attachment size limit")
    parser.add_argument("--force", action="store_true", help="Replace an existing output directory")
    args = parser.parse_args()
    try:
        result = convert_files(args.inputs, args.output_dir, args.force, args.extract_pdf, args.max_bytes)
    except (MimeError, OSError) as exc:
        print(f"MIME extraction failed: {exc}", file=sys.stderr)
        return 2
    rows = [a for m in result["messages"] for a in m["attachments"]]
    print(json.dumps({
        "messages": len(result["messages"]), "attachments": len(rows),
        "pdf_extracted": sum(a["status"] == "extracted" for a in rows),
        "needs_visual_review": sum(bool(a["needs_visual_review"]) for a in rows),
        "not_saved": sum(a["file"] is None for a in rows),
        "manifest": str(Path(args.output_dir).expanduser().resolve() / "manifest.json"),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
