# Evidence coverage and independent review

The output is **provisional** until the declared evidence has been checked and another reviewer has reviewed the final service and other-case rows against that evidence. `scripts/check_audit.py` enforces this contract. It does not establish refund eligibility, infer a charge from an invoice, prove that all accounts were discovered, or certify that a reviewer's judgment is correct.

## Files and scope

Keep this evidence bundle private. Place `audit-evidence.json` at the bundle root. All file paths in it must be relative, must point below that directory, and must resolve to nonempty files. Absolute paths, parent-directory escapes, and symlinks to outside the bundle fail the check. Preserve original mail responses and documents; record interpretations separately.

```json
{
  "scope": {
    "mode": "mailbox",
    "description": "All available Acme merchant mail, including archived, spam and trash messages, reviewed through the stated date.",
    "as_of": "2026-09-16"
  },
  "searches": [
    {
      "id": "acme-discovery-page-1",
      "service_ids": ["acme"],
      "kind": "merchant_discovery",
      "query": "in:anywhere (from:acme.example OR Acme)",
      "result_file": "searches/acme-1.json"
    }
  ],
  "sources": [
    {
      "id": "gmail:message-1",
      "service_ids": ["acme"],
      "kind": "message",
      "file": "messages/message-1.json",
      "disposition": "reviewed",
      "note": "Read full MIME and attached invoice. The email states an amount due; no successful payment was established."
    },
    {
      "id": "acme-invoice-pdf",
      "parent_id": "gmail:message-1",
      "attachment_id": "exact-gmail-attachment-id",
      "service_ids": ["acme"],
      "kind": "attachment",
      "file": "attachments/invoice.pdf",
      "disposition": "reviewed",
      "note": "Reviewed invoice issue date, service period, line items, payment status and totals."
    }
  ],
  "independent_review_file": "independent-review.json"
}
```

`mode` is `mailbox` or `files`. Use `files` only when the user supplied a finite set of documents and no mailbox-wide claim is made. Describe those supplied files and limitations precisely; keep `searches: []` and declare each supplied source. A files-only pass is not evidence of a complete mailbox audit.

## Search coverage

Every mailbox service and other case needs a broad `merchant_discovery` search. Search by merchant names, sender domains and aliases before narrowing to billing terms. Do not discover subscriptions using only English `invoice`, `receipt`, `payment`, `paid`, `charge`, or `billing` keywords: those searches miss localized invoices and lifecycle notices. The checker rejects these obvious English restrictions in discovery queries, but it cannot prove that a query contains every merchant alias or is semantically broad enough. The reviewer must assess that coverage.

Additional searches use `kind: "billing"` or `"lifecycle"`. Preserve the exact query and actual raw tool result for every page. Supported raw result forms are `{"structuredContent":{"emails":[{"id":"..."}],"next_page_token":null}}` or an equivalent direct object with `emails[]` or `ids[]`. The checker reads the saved IDs and pagination token; manually supplied counts are not a substitute.

Search entries must use `result_file`; source entries must use `file`. A source-style `file` key on a search, or a search-style `result_file` key on a source, is rejected as ambiguous. Evidence hashing reads the collection-specific field used by the checker, so an extra field cannot substitute unrelated bytes for the actual reviewed search result or source.

If a result contains a next-page token, record the next request with the **same query**, `request_page_token` equal to that exact token, and its own `result_file`. Continue until the raw result has no next-page token. Missing, orphaned, disconnected or cyclic pages fail. Every returned message ID must have a source entry and a reason, regardless of subject language. IDs may be the raw Gmail ID or `gmail:` followed by that ID.

`service_ids` associates a search or source with IDs from either report `subscriptions` or `other_cases`. Other cases, including deposits and pending refunds, must not bypass the gate. For a search covering multiple services or cases, triage every returned message for that entire declared set; split searches when that association is too broad. Search entries are not a claim that a receipt or a refund exists.

## Source dispositions and attachments

Source kinds are `message`, `attachment`, `account_page`, and `document`. Each source requires an ID, service associations, disposition and explanatory note:

| Disposition | Meaning and gate behavior |
|---|---|
| `reviewed` | Relevant content was read. A saved, accessible file and independent review coverage are required. |
| `irrelevant` | Explain why the result has no relevant billing or account lifecycle facts. A downloaded file is optional. |
| `unread` | Content has not been reviewed. The output remains provisional. |
| `inaccessible` | State the access problem and the affected conclusion. The output remains provisional. |

Reviewed messages must save the full Gmail MIME response, not just a snippet or search result. The checker inspects the MIME tree. Non-inline attachments and externally stored body parts require their own source disposition. Inline images identified as such by MIME headers are excluded from that requirement; other image attachments may be invoice images and must be triaged.

The checker examines each text part for omitted content. A plain-text fallback such as "HTML not supported" does not make a message complete when its HTML part declares nonzero bytes but has no saved body or external attachment reference. Empty alternatives without any actual message content also fail. Empty multipart containers are normal; attachment-only messages can pass when their meaningful attachments have been reviewed.

Attachment entries need `parent_id` matching the parent message source and `attachment_id` matching its exact MIME attachment ID. For an attachment embedded directly in MIME with no attachment ID, use its exact `part_id`. Attachments inherit all parent service associations. A relevant PDF is not reviewed merely because its enclosing message was read. If a PDF is genuinely irrelevant, explain that specifically; a generic exclusion note is not a substitute for reviewing billing evidence.

`scripts/extract_mime.py` converts a saved raw message (Gmail RAW JSON, with or without a `structuredContent` wrapper, or an `.eml` file) into this shape. Its `message.json` is a full MIME payload with decoded text bodies and base64url attachment data; attachments have no Gmail attachment ID, so they are matched by `part_id`. Each manifest message carries `evidence_sources` entries with `disposition: "unread"`, empty `service_ids` and paths relative to the helper's output directory. Place that directory below the bundle root, prefix the paths accordingly, add service IDs, and change a disposition only after the content has actually been read.

The checker confirms file presence and declared review coverage. The agent and independent reviewer remain responsible for reading PDF pages, OCR where needed, and interpreting the contents.

## Independent review bound to the report

```json
{
  "reviewer": "Independent review agent",
  "evidence_sha256": "sha256-from-evidence_digest-of-audit-evidence-json",
  "report_sha256": "sha256-from-report_digest-of-final-prepared-report",
  "services": [
    {
      "service_id": "acme",
      "service_sha256": "sha256-from-service_digest-of-final-prepared-row",
      "reviewed_source_ids": ["gmail:message-1", "acme-invoice-pdf"],
      "verdict": "pass",
      "note": "Compared the final row with the invoice and later lifecycle evidence; payment remains unknown because no successful charge evidence exists."
    }
  ],
  "issues": []
}
```

The reviewer must independently inspect evidence, not merely approve the author's summary. Per service, check:

- Merchant identity and account or billing-channel aliases; localized messages and all declared pages were considered.
- Full invoice, receipt and meaningful attachments were read; issue date, email date, service period and actual payment date are distinguished.
- Later cancellation, trial conversion, suspension, resource deletion, refund, failure or credit events are reconciled with earlier records.
- A zero-dollar invoice, paid-from-credit invoice, subscription price, top-up, or refund does not become a new cash charge without payment evidence.
- Current status, next renewal, monthly cost and refund suggestions reflect both the strongest evidence and the remaining gaps.
- Every relevant source is represented in the final service conclusion; contradictory evidence is resolved or explicitly left provisional.

Use `service_digest(row)` from `check_audit.py` after `render_dashboard.prepare(report)` has applied renderer defaults. Hash each row in both `report['subscriptions']` and `report.get('other_cases', [])`. The review `services[]` array contains all of these entities, using their existing report IDs as `service_id`. The helper hashes the entire row with canonical JSON: sorted keys, UTF-8 with `ensure_ascii=False`, and separators `(',', ':')`. No fields are excluded. Any later change to the row invalidates that review and requires re-review.

After saving the manifest and all source/search files, call `evidence_digest(path_to_audit_evidence_json)` and place its returned hex digest in `evidence_sha256`. This helper hashes canonical `scope`, `searches`, and `sources` metadata together with SHA256 hashes of the exact bytes of every declared source `file` and search `result_file`. It checks the same directory containment rule. The independent review file's contents are excluded to avoid a circular digest; it need not exist when this helper runs. Changing a PDF, message body, search result, source disposition, service association or scope after review invalidates the evidence digest. A missing digest also prevents a checked result. Hashing is an integrity check, not proof that a reviewer actually read the evidence.

Also call `report_digest(prepared_report)` and store the returned hex digest in `report_sha256`. This binds the entire substantive report, including top-level monthly cost inputs, summary, coverage and all service/case rows. It excludes **only** the `computed` field, which the renderer recomputes and which contains the transient audit-quality result. No other top-level fields are excluded. Changing the monthly cost calculation inputs or summary after review invalidates this digest even if every individual service row is unchanged. A missing report digest prevents a checked result. Compute all hashes from the same final prepared report that the reviewer assessed.

`reviewed_source_ids` must include every source marked `reviewed` for that service or other case. `verdict` is `pass` or `needs_review`; a missing row or a `needs_review` verdict prevents a checked result. Each review row needs a specific note. Global `issues` are objects with `message`, optional `service_id`, and optional `blocking`. Issues block by default; `blocking: false` is reserved for clearly nonblocking observations.

## Running the gate

```sh
python3 scripts/check_audit.py --report prepared-report.json --evidence private-evidence/audit-evidence.json --output audit-check.json
```

Use `--force` only to replace an existing check output. Exit codes: `0` checked, `2` provisional, `1` input/output or invalid report failure. The CLI applies `render_dashboard.prepare(report)` before checking so its row hashes match the renderer. The Python API `assess(report, evidence_path=None)` expects an already prepared report, returns `status`, `summary`, `issues`, `counts`, and `scope`, and does not mutate report data. Missing evidence or invalid manifest content returns provisional. Counts distinguish subscription `services`, `other_cases`, and combined `entities`; `independently_reviewed_entities` includes both types.

A checked result means the declared evidence and final rows passed these coverage checks. Display the scope and remaining factual uncertainty alongside it. Never replace unknown charges, usage, costs or refund eligibility with guessed values to make the gate pass.
