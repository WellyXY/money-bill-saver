# Evidence coverage and independent review

The output is **provisional** until the declared evidence has been checked and another reviewer has reviewed the final service and other-case rows against that evidence. `scripts/check_audit.py` enforces this contract. It does not establish refund eligibility, infer a charge from an invoice, prove that all accounts were discovered, or certify that a reviewer's judgment is correct.

## Files and scope

Keep this evidence bundle private. Place `audit-evidence.json` at the bundle root. All file paths in it must be relative, must point below that directory, and must resolve to nonempty files. Absolute paths, parent-directory escapes, and symlinks to outside the bundle fail the check. Preserve original mail responses and documents; record interpretations separately.

```json
{
  "scope": {
    "mode": "mailbox",
    "description": "Generic invoice/receipt discovery and focused billing checks, March 16–September 16, 2026; selected mailbox including archived mail, excluding spam and trash.",
    "as_of": "2026-09-16",
    "workflow_version": "audit-1",
    "audit_kind": "inventory",
    "search_plan": {
      "schema_version": "1",
      "generic_invoice_receipt": {
        "search_ids": ["generic-page-1"],
        "coverage": "all_categories",
        "note": "Generic invoice and receipt strategy, including relevant localized terms; exact query coverage is reviewed independently."
      }
    }
  },
  "searches": [
    {
      "id": "generic-page-1",
      "scope": "discovery",
      "service_ids": [],
      "kind": "billing",
      "query": "after:2026/03/16 before:2026/09/17 -in:spam -in:trash {invoice receipt 帳單 發票}",
      "result_file": "searches/generic-1.json"
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

Separate global candidate discovery from material evidence for each entity. Use `scope: "discovery"` and `service_ids: []` on generic and shared channel searches. Preserve every returned ID and triage reason globally. Associate a reviewed receipt only with its actual service or case; a shared discovery query must not make that receipt evidence for every entity. Irrelevant or still-unread candidates whose entity is unknown may have `service_ids: []`. An unread candidate still blocks completion. Reviewed or inaccessible material sources require known entity IDs.

Every mailbox service and other case needs either a relevant returned source in a complete discovery query or a saved targeted `billing` or `lifecycle` search. A user-named service with no material source needs its own targeted query, which may return no results. Use targeted sender/account/thread checks for material gaps and state changes. Follow [email-search-checklist.md](email-search-checklist.md) for the default period, query choices and stopping condition. Automatic unrestricted merchant discovery is not part of the default workflow. The legacy `merchant_discovery` kind remains accepted. Searches without a `scope` retain legacy entity-associated behavior; `scope: "entity"` is its explicit equivalent.

New canonical mailbox inventory reports use `scope.workflow_version: "audit-1"`, `scope.audit_kind: "inventory"` and the exact versioned `search_plan` shape above. Missing `audit_kind` defaults to `inventory`. The plan's `generic_invoice_receipt.search_ids` is a nonempty list of distinct saved **first-page** discovery IDs. Each must reference a complete query chain. `coverage` is `all_categories`: generic invoice/receipt discovery must supplement category and payment-channel searches, so a Cloudflare-like invoice delivered outside purchases can still be found. Unsupported search capability, missing pages or an unexecuted plan remains provisional; never create an empty successful response to satisfy this declaration. Legacy bundles without the workflow marker remain supported. A supplied search plan is validated even on a legacy bundle.

A single-charge or otherwise narrow recovery task can use `scope.audit_kind: "targeted"`, with the actual narrow boundary in `scope.description`. It requires saved targeted query coverage for each reported entity, including an explicit no-result query when appropriate, but does not require generic mailbox-wide discovery or a `search_plan`. A global discovery hit alone does not replace the targeted query. The reviewer checks that this declared scope matches the user's task; use targeted mode because the task is narrow, not to evade inventory coverage.

The gate validates the declared strategy, exact results, associations and pagination. It does **not** establish semantic query sufficiency through keyword regular expressions. The independent reviewer must compare the actual query with the all-category invoice/receipt strategy, relevant languages, time/account boundaries and observed source gaps. Unknown facts may remain unknown after completed scoped review; unread material evidence cannot pass.

Preserve the exact query and actual raw tool result for every page. Supported raw result forms are `{"structuredContent":{"emails":[{"id":"..."}],"next_page_token":null}}` or an equivalent direct object with `emails[]` or `ids[]`. The checker reads the saved IDs and pagination token; manually supplied counts are not a substitute. A saved no-result search is valid scope evidence, not proof that a named service does not exist.

Search entries must use `result_file`; source entries must use `file`. A source-style `file` key on a search, or a search-style `result_file` key on a source, is rejected as ambiguous. Evidence hashing reads the collection-specific field used by the checker, so an extra field cannot substitute unrelated bytes for the actual reviewed search result or source.

If a result contains a next-page token, record the next request with the **same query**, `request_page_token` equal to that exact token, and its own `result_file`. Continue until the raw result has no next-page token. Missing, orphaned, disconnected or cyclic pages fail. Every returned message ID must have a source entry and a reason, regardless of subject language. IDs may be the raw Gmail ID or `gmail:` followed by that ID.

`service_ids` refers to IDs from either report `subscriptions` or `other_cases`. Other cases, including deposits and pending refunds, must not bypass the gate. Discovery pages keep the same empty associations and `scope` across their chain. Legacy/entity-scoped searches retain their material-result association requirements; use discovery scope for shared queries rather than assigning unrelated results to all entities. A documented globally irrelevant candidate stays excluded once even if it also appears in targeted results. An unassigned unread candidate also stays global and provisional until triaged; a reviewed material result bound to the wrong entity fails. Search entries are not a claim that a receipt or refund exists.

## Source dispositions and attachments

Source kinds are `message`, `attachment`, `account_page`, and `document`. Each source requires an ID, service associations, disposition and explanatory note:

| Disposition | Meaning and gate behavior |
|---|---|
| `reviewed` | Relevant content was read. A saved, accessible file and independent review coverage are required. |
| `irrelevant` | Explain why the result has no relevant billing or account lifecycle facts. A downloaded file is optional. |
| `unread` | Content has not been reviewed. The output remains provisional. |
| `inaccessible` | State the access problem and the affected conclusion. The output remains provisional. |

Reviewed messages must save the full Gmail MIME response or a validated conversion from an original raw message, not just a snippet or search result. The checker inspects the MIME tree. Attachments, externally stored body parts, attached messages and inline images require their own source disposition. A Content-ID or inline disposition does not establish irrelevance: inspect potential invoice images, and explicitly mark confirmed logos or decorations irrelevant with a reason.

The checker examines each text part for omitted content. A plain-text fallback such as "HTML not supported" does not make a message complete when its HTML part declares nonzero bytes but has no saved body or external attachment reference. Empty alternatives without any actual message content also fail. Empty multipart containers are normal; attachment-only messages can pass when their meaningful attachments have been reviewed.

Attachment entries need `parent_id` matching the parent message source and `attachment_id` matching its exact MIME attachment ID. For an attachment embedded directly in MIME with no attachment ID, use its exact `part_id`. Attachments inherit all parent service associations. A relevant PDF is not reviewed merely because its enclosing message was read. If a PDF is genuinely irrelevant, explain that specifically; a generic exclusion note is not a substitute for reviewing billing evidence.

### Converted raw messages

`scripts/extract_mime.py` converts saved Gmail RAW JSON (direct or wrapped in `structuredContent`) or an `.eml` file into a full MIME `message.json`. The original input is saved alongside the conversion. Raw MIME parts have deterministic tree-based `part_id` values, rather than invented Gmail attachment IDs; keep the helper's parent/part associations when integrating them.

Each manifest message carries suggested `evidence_sources` entries with empty `service_ids` and paths relative to the helper's output directory. Place that directory below the bundle root, prefix each source `file` accordingly, and add the appropriate service IDs. Extraction starts sources as `unread` (or `inaccessible` when an attachment cannot be saved). Change a disposition only after the content has actually been read. A helper manifest describes its supplied messages; it does not replace scoped search coverage, pagination, factual analysis or independent review.

Converted `message.json` records contain `extraction.schema_version: "1"` and `extraction.files`. Each file record contains `role`, `file` and its exact-byte `sha256`. There is exactly one `original` input, plus the body text, saved attachments and generated attachment text/PDF artifacts. These paths are relative to the directory containing `message.json`; keep them unchanged when moving the whole bundle. They must remain within that message directory and the audit bundle. The checker validates these files and includes their bytes in the evidence digest. Keep `message.json` out of its own file list to avoid a circular hash. `raw_sha256` records the decoded original email bytes; a stored hash alone is not a substitute for the original file.

MIME conversion errors and unresolved truncation cannot become a complete-message claim. Decoding warnings require examining the affected content before marking it reviewed; complete file retrieval and successful text extraction do not establish correct invoice interpretation.

The checker confirms file presence and declared review coverage. Read reliable extracted text first. Scanned pages, decoding warnings, suspicious control characters and conflicting material amounts/identifiers require examination of the relevant original pages, with OCR when useful. Do not render every page merely because a PDF exists. Record which material fields/pages were checked; extraction and packet creation never set a source to reviewed automatically. Preserve any alternate extraction outside sealed conversion folders and declare it as a document source if it supports conclusions.

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
      "entity_evidence_sha256": "sha256-from-entity_evidence_digest-for-acme",
      "reviewed_source_ids": ["gmail:message-1", "acme-invoice-pdf"],
      "verdict": "pass",
      "note": "Compared the final row with the invoice and later lifecycle evidence; payment remains unknown because no successful charge evidence exists."
    }
  ],
  "issues": []
}
```

The reviewer must independently inspect evidence, not merely approve the author's summary. Per service, check:

- Merchant identity, account and known billing-channel aliases; relevant source languages, selected period and declared pages were considered. Evaluate conclusions within that scope rather than requiring an unrestricted merchant sweep.
- Full invoice, receipt and meaningful attachments were read; issue date, email date, service period and actual payment date are distinguished.
- Later cancellation, trial conversion, suspension, resource deletion, refund, failure or credit events are reconciled with earlier records.
- A zero-dollar invoice, paid-from-credit invoice, subscription price, top-up, or refund does not become a new cash charge without payment evidence.
- Current status, next renewal, monthly cost and refund suggestions reflect both the strongest evidence and the remaining gaps.
- Every relevant source is represented in the final service conclusion; contradictory evidence is resolved or explicitly left provisional.

Use `service_digest(row)` from `check_audit.py` after `render_dashboard.prepare(report)` has applied renderer defaults. Hash each row in both `report['subscriptions']` and `report.get('other_cases', [])`. The review `services[]` array contains all of these entities, using their existing report IDs as `service_id`. The helper hashes the entire row with canonical JSON: sorted keys, UTF-8 with `ensure_ascii=False`, and separators `(',', ':')`. No fields are excluded. Any later change to the row invalidates that review and requires re-review.

For workflow `audit-1`, each review row also requires `entity_evidence_sha256`, returned by `entity_evidence_digest(evidence_path, service_id)`. It binds the metadata and file bytes of associated material sources, including unread/inaccessible ones when present and all original/derived converted-message files. Irrelevant candidates and global discovery remain in the global evidence digest. Legacy reviews may omit the entity digest; when supplied, it is checked. Changing an entity's material evidence requires re-review of that entity even if someone updates the global digest.

After saving the manifest and all source/search files, call `evidence_digest(path_to_audit_evidence_json)` and place its returned hex digest in `evidence_sha256`. This helper hashes canonical `scope`, `searches`, and `sources` metadata together with SHA256 hashes of every declared source `file`, search `result_file`, and the original/derived files declared by converted messages. It validates the file hashes and directory containment rules. The independent review file's contents are excluded to avoid a circular digest; it need not exist when this helper runs. Changing an original email, extracted text, PDF, message body, search result, source disposition, service association or scope after review invalidates the evidence binding. A missing digest also prevents a checked result. Hashing establishes integrity, not sender authenticity or proof that a reviewer read the evidence.

Also call `report_digest(prepared_report)` and store the returned hex digest in `report_sha256`. This binds the entire substantive report, including top-level monthly cost inputs, summary, coverage and all service/case rows. It excludes **only** the `computed` field, which the renderer recomputes and which contains the transient audit-quality result. No other top-level fields are excluded. Changing the monthly cost calculation inputs or summary after review invalidates this digest even if every individual service row is unchanged. A missing report digest prevents a checked result. Compute all hashes from the same final prepared report that the reviewer assessed.

`reviewed_source_ids` must include every source marked `reviewed` for that service or other case. `verdict` is `pass` or `needs_review`; a missing row or a `needs_review` verdict prevents a checked result. Each review row needs a specific note. Global `issues` are objects with `message`, optional `service_id`, and optional `blocking`. Issues block by default; `blocking: false` is reserved for clearly nonblocking observations.

### Prepare focused review packets

```sh
python3 scripts/prepare_review.py --report prepared-report.json --evidence audit-evidence.json --output-dir review-packets
```

The helper writes owner-only entity packets and `global-review.json`. Each entity packet contains the prepared row, its hashes, associated material source records and exact original/derived file paths and hashes. The global packet contains exact search records, candidate/disposition counts, irrelevant and unassigned candidates, unresolved sources, report-wide monthly inputs and coverage, plus gate diagnostics. Review actual originals; packet source dispositions are the author's declarations, not reviewer approval.

Pass `--previous-review independent-review.json` to compare against an earlier review. Changed row/evidence hashes identify the entities requiring new review; unchanged entity reviews can be retained after confirming their bindings. Independently reassess changed global discovery, monthly inputs, summary and coverage before binding the final `evidence_sha256` and `report_sha256`. Every final entity still needs its own valid review row. The helper never creates a reviewer verdict, marks content read, or silently carries a pass forward. `--force` replaces only recognizable files generated by this helper, after preflighting every target; it refuses collisions with the report, prior review, manifest, search results or original/derived evidence. The global index lists the current packet set. Irrelevant sources appear once in the global exclusion list, rather than again as unassigned candidates.

## Running the gate

```sh
python3 scripts/check_audit.py --report prepared-report.json --evidence private-evidence/audit-evidence.json --output audit-check.json
```

Use `--force` only to replace an existing check output. Exit codes: `0` checked, `2` provisional, `1` input/output or invalid report failure. The CLI applies `render_dashboard.prepare(report)` before checking so its row hashes match the renderer. The Python API `assess(report, evidence_path=None)` expects an already prepared report, returns `status`, `summary`, `issues`, `counts`, and `scope`, and does not mutate report data. Missing evidence or invalid manifest content returns provisional. Counts distinguish subscription `services`, `other_cases`, and combined `entities`; `independently_reviewed_entities` includes both types.

A checked result means the declared evidence and final rows passed these coverage checks. Display the scope and remaining factual uncertainty alongside it. Never replace unknown charges, usage, costs or refund eligibility with guessed values to make the gate pass.
