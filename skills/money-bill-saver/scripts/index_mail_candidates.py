#!/usr/bin/env python3
"""Build a private, offline index of saved mailbox search results.

This is a routing aid, not a billing classifier. Unknown metadata stays unknown.
Stdout contains counts only; subjects and message IDs appear only in the output.
"""

import argparse
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import tempfile


class CandidateIndexError(ValueError):
    pass


def _payload(value):
    if isinstance(value, dict) and isinstance(value.get("structuredContent"), dict):
        return value["structuredContent"]
    return value


def _pages(data):
    if not isinstance(data, dict):
        raise CandidateIndexError("input must be a JSON object")
    pages = data.get("pages")
    if pages is None:
        yield data.get("page", 1), data.get("query"), _payload(data)
    elif isinstance(pages, list):
        for number, page in enumerate(pages, 1):
            if not isinstance(page, dict):
                yield number, data.get("query"), None
                continue
            response = page.get("response", page)
            yield page.get("page", number), page.get("query", data.get("query")), _payload(response)
    else:
        raise CandidateIndexError("pages must be an array")


def _records(page):
    if not isinstance(page, dict):
        return None
    fields = ("emails", "messages", "message_ids", "ids")
    present = [key for key in fields if key in page]
    if not present:
        return None
    result = []
    for key in present:
        if not isinstance(page[key], list):
            return None
        result.extend(page[key])
    return result


def _assess_run(data, pages, path):
    """Check saved search pagination without exposing page tokens in the index."""
    reasons = []
    unknown_reasons = []

    def mark(reason):
        if reason not in reasons:
            reasons.append(reason)

    if data.get("isError") or data.get("error"):
        mark("search_error")
    if not isinstance(data.get("query"), str) or not data["query"].strip():
        unknown_reasons.append("missing_query")
    bundle = isinstance(data.get("pages"), list)
    if bundle:
        raw_pages = data["pages"]
        if not raw_pages:
            mark("empty_pages")
        expected = None
        seen_tokens = set()
        for number, raw in enumerate(raw_pages, 1):
            if not isinstance(raw, dict):
                mark("invalid_page")
                continue
            if raw.get("page", number) != number:
                mark("page_number_gap")
            if "query" in raw and raw["query"] != data.get("query"):
                mark("query_mismatch")
            request = raw.get("request_next_page_token")
            if number == 1 and request not in (None, ""):
                mark("missing_first_page")
            elif number > 1:
                if expected in (None, ""):
                    mark("unexpected_extra_page")
                elif request != expected:
                    mark("token_mismatch")
            response = raw.get("response", raw)
            if isinstance(response, dict) and (response.get("isError") or response.get("error")):
                mark("tool_error")
            payload = _payload(response)
            if not isinstance(payload, dict):
                mark("invalid_page")
                expected = None
                continue
            if payload.get("isError") or payload.get("error"):
                mark("tool_error")
            if "next_page_token" not in payload:
                mark("missing_next_token_field")
                expected = None
                continue
            following = payload["next_page_token"]
            if following not in (None, "") and not isinstance(following, str):
                mark("invalid_token")
                expected = None
                continue
            if following not in (None, ""):
                if following in seen_tokens or following == request:
                    mark("token_cycle")
                seen_tokens.add(following)
            expected = following
        if expected not in (None, ""):
            mark("missing_continuation")
    else:
        payload = _payload(data)
        if not isinstance(payload, dict):
            mark("invalid_page")
        elif payload.get("isError") or payload.get("error"):
            mark("tool_error")
        elif "next_page_token" not in payload:
            unknown_reasons.append("missing_next_token_field")
        elif payload["next_page_token"] not in (None, ""):
            mark("missing_continuation")
    if data.get("completed") is False:
        mark("completed_flag_false")
    status = "incomplete" if reasons else ("unknown" if unknown_reasons else "complete")
    return {"file": str(Path(path).resolve()), "query": data.get("query"),
            "page_count": len(pages), "status": status,
            "reasons": reasons + unknown_reasons}


def _header(record, name):
    headers = record.get("headers")
    if not isinstance(headers, list):
        payload = record.get("payload")
        headers = payload.get("headers") if isinstance(payload, dict) else None
    if isinstance(headers, list):
        for header in headers:
            if isinstance(header, dict) and str(header.get("name", "")).lower() == name:
                return header.get("value")
    return None


def _first(record, *names):
    for name in names:
        value = record.get(name)
        if value is not None and value != "":
            return value
    return None


def _sender(record):
    value = _first(record, "sender_email", "from_email", "from_", "from", "sender") or _header(record, "from")
    if isinstance(value, dict):
        value = _first(value, "email", "address")
    address = parseaddr(value)[1].lower() if isinstance(value, str) else ""
    if "@" not in address:
        return None, None
    return address, address.rsplit("@", 1)[1]


def _date(value):
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            number = float(value)
            if number > 1e11:
                number /= 1000
            parsed = datetime.fromtimestamp(number, tz=timezone.utc)
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = parsedate_to_datetime(value)
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, TypeError, ValueError):
        return None


def _subject_pattern(subject):
    """Conservative navigation bucket; never a merchant or bill classification."""
    if not subject:
        return None
    value = subject.casefold().strip()
    value = re.sub(r"^(?:(?:re|fw|fwd)\s*:\s*)+", "", value)
    value = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", "<date>", value)
    value = re.sub(r"\b\d{4,}\b", "<number>", value)
    return re.sub(r"\s+", " ", value).strip() or None


def _attachment_flag(record):
    value = _first(record, "has_attachment", "has_attachments", "hasAttachments")
    if isinstance(value, bool):
        return value
    for key in ("attachments", "attachment_ids", "attachmentIds"):
        if key in record and isinstance(record[key], list):
            return bool(record[key])
    return None


def _metadata(record):
    if not isinstance(record, dict):
        return {"sender_email": None, "sender_domain": None, "subject": None, "snippet": None,
                "date": None, "has_attachments": None}
    sender, domain = _sender(record)
    subject = _first(record, "subject") or _header(record, "subject")
    snippet = _first(record, "snippet")
    date = _date(_first(record, "email_ts", "date", "received_at", "receivedAt", "internalDate") or _header(record, "date"))
    return {"sender_email": sender, "sender_domain": domain,
            "subject": str(subject) if subject is not None else None,
            "snippet": str(snippet) if snippet is not None else None,
            "date": date, "has_attachments": _attachment_flag(record)}


def _groups(messages, key, label):
    grouped = {}
    for message in messages:
        value = message.get(key)
        if value:
            grouped.setdefault(value, []).append(message)
    result = []
    for value, items in grouped.items():
        ordered = sorted(items, key=lambda item: item.get("date") or "", reverse=True)
        examples = []
        for item in ordered:
            subject = item.get("subject")
            if subject and subject not in examples:
                examples.append(subject)
            if len(examples) == 3:
                break
        dates = [item["date"] for item in items if item.get("date")]
        result.append({label: value, "message_count": len(items),
                       "newest_date": max(dates) if dates else None,
                       "subject_examples": examples,
                       "message_ids": [item["id"] for item in ordered]})
    return sorted(result, key=lambda group: (-group["message_count"], group[label]))


def _subject_groups(messages):
    grouped = {}
    for message in messages:
        domain = message.get("sender_domain")
        pattern = _subject_pattern(message.get("subject"))
        if domain and pattern:
            grouped.setdefault((domain, pattern), []).append(message)
    result = []
    for (domain, pattern), items in grouped.items():
        ordered = sorted(items, key=lambda item: item.get("date") or "", reverse=True)
        examples = []
        for item in ordered:
            if item["subject"] not in examples:
                examples.append(item["subject"])
            if len(examples) == 3:
                break
        result.append({"sender_domain": domain, "subject_pattern": pattern,
                       "message_count": len(items),
                       "newest_date": next((item["date"] for item in ordered if item.get("date")), None),
                       "subject_examples": examples,
                       "message_ids": [item["id"] for item in ordered]})
    return sorted(result, key=lambda group: (-group["message_count"],
                                             group["sender_domain"], group["subject_pattern"]))


def build_index(paths):
    messages = {}
    invalid_pages = invalid_records = page_count = 0
    query_runs = []
    mailboxes = set()
    unspecified_mailbox = False
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CandidateIndexError(f"could not read JSON input: {Path(path).name}") from exc
        pages = list(_pages(data))
        mailbox = data.get("mailbox")
        if isinstance(mailbox, str) and mailbox.strip():
            mailboxes.add(mailbox.strip().casefold())
        else:
            unspecified_mailbox = True
        if len(mailboxes) > 1 or (mailboxes and unspecified_mailbox):
            raise CandidateIndexError("input files must belong to one mailbox; build a separate index per mailbox")
        run = _assess_run(data, pages, path)
        for number, query, page in pages:
            page_count += 1
            records = _records(page)
            if records is None:
                invalid_pages += 1
                if "invalid_page" not in run["reasons"]:
                    run["reasons"].append("invalid_page")
                run["status"] = "incomplete"
                continue
            for record in records:
                if isinstance(record, str):
                    message_id = record.strip()
                elif isinstance(record, dict):
                    message_id = _first(record, "id", "message_id", "messageId")
                else:
                    message_id = None
                if not isinstance(message_id, str) or not message_id.strip():
                    invalid_records += 1
                    if "invalid_record" not in run["reasons"]:
                        run["reasons"].append("invalid_record")
                    run["status"] = "incomplete"
                    continue
                message_id = message_id.strip()
                values = _metadata(record)
                entry = messages.setdefault(message_id, {"id": message_id,
                    "sender_email": None, "sender_domain": None, "subject": None, "snippet": None,
                    "date": None, "has_attachments": None, "seen_in": []})
                for key, value in values.items():
                    if entry[key] is None and value is not None:
                        entry[key] = value
                provenance = {"file": str(Path(path).resolve()), "query": query, "page": number}
                if provenance not in entry["seen_in"]:
                    entry["seen_in"].append(provenance)
        query_runs.append(run)
    ordered = sorted(messages.values(), key=lambda entry: (entry.get("date") or "", entry["id"]), reverse=True)
    for entry in ordered:
        entry["missing_metadata"] = [key for key in ("sender_email", "subject", "date", "has_attachments")
                                     if entry[key] is None]
        entry["needs_metadata_fetch"] = bool(entry["missing_metadata"])
        entry["id_only"] = all(entry[key] is None for key in
                               ("sender_email", "subject", "snippet", "date", "has_attachments"))
    incomplete_queries = sum(run["status"] == "incomplete" for run in query_runs)
    coverage_unknown = sum(run["status"] == "unknown" for run in query_runs)
    return {"schema_version": 1, "navigation_only": True,
            "input_files": len(paths), "pages": page_count,
            "saved_query_pages_complete": bool(query_runs) and not incomplete_queries and not coverage_unknown,
            "complete_queries": sum(run["status"] == "complete" for run in query_runs),
            "incomplete_queries": incomplete_queries, "coverage_unknown": coverage_unknown,
            "query_runs": query_runs,
            "message_count": len(ordered), "id_only_count": sum(item["id_only"] for item in ordered),
            "needs_metadata_fetch_count": sum(item["needs_metadata_fetch"] for item in ordered),
            "unknown_sender_count": sum(item["sender_email"] is None for item in ordered),
            "invalid_pages": invalid_pages, "invalid_records": invalid_records,
            "messages": ordered,
            "senders": _groups(ordered, "sender_email", "sender_email"),
            "domains": _groups(ordered, "sender_domain", "sender_domain"),
            "subject_patterns": _subject_groups(ordered)}


def build_summary(index):
    limits = {"senders": 40, "domains": 100, "subject_patterns": 30}
    summary = {key: index[key] for key in (
        "schema_version", "navigation_only", "input_files", "pages",
        "saved_query_pages_complete", "complete_queries", "incomplete_queries", "coverage_unknown",
        "message_count", "id_only_count", "needs_metadata_fetch_count", "unknown_sender_count",
        "invalid_pages", "invalid_records")}
    summary["query_runs"] = [{key: run[key] for key in ("query", "page_count", "status", "reasons")}
                             for run in index["query_runs"]]
    summary["omitted_groups"] = {}
    for group_name, limit in limits.items():
        summary["omitted_groups"][group_name] = max(0, len(index[group_name]) - limit)
        rows = []
        for position, group in enumerate(index[group_name][:limit]):
            row = {"message_count": group["message_count"]}
            if group_name == "senders":
                row["sender_email"] = group["sender_email"]
                if position < 20 and group["subject_examples"]:
                    row["subject_example_preview"] = group["subject_examples"][0][:80]
            elif group_name == "domains":
                row["sender_domain"] = group["sender_domain"]
            else:
                row["sender_domain"] = group["sender_domain"]
                row["subject_pattern_preview"] = group["subject_pattern"][:120]
            rows.append(row)
        summary[group_name] = rows
    return summary


def _write_private(path, data):
    path = Path(path)
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            continue
        os.chmod(directory, 0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, type=Path,
                        help="saved JSON search result; repeat for each file")
    parser.add_argument("--output", required=True, type=Path,
                        help="private candidate-index.json")
    parser.add_argument("--summary-output", type=Path,
                        help="optional private group summary without message rows or IDs")
    args = parser.parse_args(argv)
    try:
        if args.summary_output and args.output.resolve() == args.summary_output.resolve():
            raise CandidateIndexError("summary output must differ from full output")
        index = build_index(args.input)
        _write_private(args.output, index)
        if args.summary_output:
            _write_private(args.summary_output, build_summary(index))
    except (CandidateIndexError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"Indexed {index['message_count']} unique messages from {index['pages']} pages; "
          f"{index['id_only_count']} have IDs only; "
          f"{index['complete_queries']} complete, {index['incomplete_queries']} incomplete, "
          f"{index['coverage_unknown']} unknown search runs; "
          f"{index['invalid_pages']} invalid pages; {index['invalid_records']} invalid records.")
    if not index["saved_query_pages_complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
