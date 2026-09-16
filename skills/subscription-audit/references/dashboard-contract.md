# Visual subscription document contract

Use this contract for `dashboard.json`, then render a private, self-contained `dashboard.html`. It is a presentation model derived from the sourced inventory and cases; it does not replace `facts.json`, `checks.json` or the outcome ledger.

## Three-section presentation

A full audit always shows these sections in order:

1. **Current services:** every row from `subscriptions`, with uncertain/historical states labeled. User-named services remain visible even without a receipt.
2. **Refund questions:** rows from either `subscriptions` or `other_cases` classified as `review_group: refund`. Each has a specific sourced reason, amount under review, eligibility state, missing evidence and next step/draft; inclusion does not mean a refund is guaranteed.
3. **Other issues:** rows from either array classified as `review_group: other`, such as renewal decisions, unknown fees, benefits, reimbursements, usage/dependency checks and source gaps.

Keep explicit empty states for empty sections. Do not use other issues to fill an empty refund section. Inventory visibility is independent of issue grouping: a service remains in the first section even when it also appears in a later section. `priority` can affect emphasis but must not hide classified issues.

## Render

Resolve the script and input/output paths from the installed skill and task directory:

```text
python scripts/render_dashboard.py --input dashboard.json --output dashboard.html
```

Use absolute paths when running the command. Existing output requires `--force`. The renderer reads `assets/dashboard.html`, embeds the supplied JSON with HTML delimiters escaped, computes selected counts/subtotals and writes a local HTML file with owner-only permissions. It makes no network requests. Opening an explicit evidence or support link navigates to that destination; copying a draft does not submit it.

The template uses local CSS/JavaScript and system fonts. Keep it self-contained: no remotely loaded fonts, analytics, raw email HTML or tracking images. The provided interface is Traditional Chinese; localize the template when needed for the user's requested language while preserving its data and action boundaries. Publishing private dashboard data requires separate authorization.

## Top-level object

| Field | Type | Meaning |
|---|---|---|
| `title` | string | User-facing document title |
| `intro` | string | Short description of what the inventory lets the user decide |
| `as_of` | string | Audit date, preferably ISO date; not a claim of live account access |
| `status_boundary` | string | Visible distinction between evidence-supported status and unchecked account state |
| `cost_boundary` | string | Visible limits of the fixed monthly subtotal |
| `subscriptions` | array | All observed continuing services in scope, plus user-named services with missing evidence |
| `other_cases` | array | Reimbursements, deposits, one-time refunds and other non-subscription cases |
| `appendix` | array | Remaining bill/source groups with `name`, `category` and `note` strings |
| `coverage` | object | `summary` string and `notes` array of strings describing source accounts, dates, counts, omissions and unsupported attachments |
| `footer_note` | string | Concise provenance or outcome qualification |

`subscriptions` is required by the renderer. Populate the other fields needed for a coherent document. Empty arrays are appropriate when there are no items; never invent an item to fill a section. Additional provenance fields may be retained in JSON even when the template does not display them.

Keep the `subscriptions` list focused on subscription or continuing-service decisions. Candidate services can remain visible with uncertain status; generic bank/payment channels and incoming reimbursements belong elsewhere. Completeness refers to the documented sources and user-named services, not an assertion that every actual account has been discovered.

## Subscription and case rows

Both `subscriptions` and `other_cases` use the same display fields. Give every row a stable, globally unique `id` so detail controls cannot select the wrong case.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable local service/case reference |
| `name` | string | Recognizable service name; include seller name when needed to connect invoices |
| `initials` | string, optional | Short text mark for the service row |
| `category` | string | Service or case type |
| `plan` | string or null | Latest supported plan; qualify conflicting or stale plan signals |
| `status` | enum | `observed`, `uncertain`, `user_reported` or `historical`, as defined below |
| `status_label` | string | Precise user-facing state, such as a covered paid period or status awaiting confirmation |
| `status_note` | string | Evidence date, state basis and remaining account-state uncertainty |
| `cost` | object | Display and subtotal fields below |
| `renewal` | string or null | Explicit date/type/basis; distinguish renewal, trial end, term end and inferred dates |
| `needs_action` | boolean | Whether this row requires a user check or proposed action |
| `review_group` | enum, optional | `refund`, `other` or `none`; determines the issue section as specified below |
| `refund_review` | object | Required structured refund question when `review_group` is `refund` |
| `priority` | boolean, optional | Emphasis/order hint only; does not decide whether a classified issue is displayed |
| `issue` | object | `title`, `summary` and optional `detail` strings; an unknown or resolved finding is valid |
| `action` | object | `summary`, `steps` array of strings, and optional official `url` and `link_label` |
| `evidence` | array | Dated sources/time sequence with fields below |
| `unknowns` | array of strings | Specific evidence needed for a stronger conclusion |
| `drafts` | array | Available, current local drafts with fields below |

The status codes express the basis for the view:

- `observed`: evidence supports a relevant current period, entitlement or recent service activity as of the audit date. State the exact basis; it does not by itself prove current login activity, continuing renewal or bank settlement.
- `uncertain`: a service/plan/trial signal exists but present paid status is unresolved.
- `user_reported`: the user names the service, but no adequate independent status evidence has been found.
- `historical`: the row is retained as past history and is not counted as a current paid service.

Never encode unknown price or current state as zero or inactive. A disabled auto-renew setting is separate from the remaining prepaid service term. Where later evidence changes a finding, show the updated state and retain the earlier events in `evidence`; omit a draft that relies on the superseded state.

### Review group and refund basis

Use explicit `review_group` values in newly authored data:

- `refund`: a specific refund-related concern supported by at least one source, including an unresolved possible overcharge, duplicate payment, attributed unused paid period, or existing refund awaiting receipt. Set `needs_action: true`, supply a nonempty `evidence` array and populate `refund_review` below. A receipt alone does not prove the concern or eligibility; explain what it supports and what remains unverified.
- `other`: an actionable renewal, unknown fee, missing benefit, reimbursement, usage/dependency issue or data gap without a specific refund question.
- `none`: no current issue to put in either issue section. The service still remains in the inventory, including normal or resolved entries.

For older inputs without `review_group`, the effective group is `other` when `needs_action` is true, otherwise `none`. For `other_cases`, missing `needs_action` defaults to true; for subscription rows it does not. Use explicit booleans when authoring new data. These defaults never infer a refund opportunity.

`refund_review` contains:

| Field | Type | Meaning |
|---|---|---|
| `reason` | nonempty string | Specific concern and its evidence basis; distinguish source facts, inference and user-reported non-use |
| `amount_label` | nonempty string | Amount/currency and what it represents, or explicit unknown; not a promised recovery amount |
| `eligibility` | enum | `unverified`, `policy_supported`, `goodwill` or `refund_pending` |
| `missing_evidence` | array of strings, optional | Facts needed to resolve the concern, establish eligibility or verify receipt |

Interpret the eligibility states as follows:

- `unverified`: the concern merits review but entitlement, payment or another necessary fact is unresolved.
- `policy_supported`: cited applicable terms and evidence support a request; state any remaining conditions and do not guarantee acceptance.
- `goodwill`: request an exception without asserting entitlement, using a credible source-backed or clearly attributed explanation.
- `refund_pending`: trace an existing refund decision/processing event; distinguish merchant status from actual receipt and do not count it as newly recovered by this audit.

Use the row's `action` and `drafts` for the next step and conditional request. Explain missing facts in `missing_evidence` even when the amount is known. Ordinary incoming reimbursements and benefit activation belong in other issues unless a separate, specific refund of a user-paid charge is supported. If one service has separate refund and other issues, keep the canonical service in `subscriptions` and represent the distinct additional case with its own stable ID in `other_cases`; retain the service/case linkage in JSON and avoid counting the same concern twice.

### Cost object

| Field | Type | Meaning |
|---|---|---|
| `label` | string | Human-readable cost and cycle, or an explicit unknown |
| `note` | string | Whether the amount is plan price, tax-inclusive payment, variable usage, prepaid total, equivalent or historical amount |
| `kind` | string | Use `fixed_monthly` for a supported fixed monthly price; other clear kinds can include `variable_usage`, `prepaid`, `multi_month`, `annual`, `historical` and `unknown` |
| `amount` | decimal string or null | Numeric amount without currency symbols, only when known |
| `currency` | uppercase three-letter string or null | Currency of a known monetary amount; do not substitute points for money |
| `include_monthly` | boolean | Opt in to the computed fixed monthly subtotal only when the conditions below hold |

Set `include_monthly: true` only for an `observed` row with `kind: fixed_monthly`, a source-backed monthly amount/currency and nonempty `evidence`. Include account-specific price/cycle evidence, not a public advertised price. The renderer rejects a counted row without these structural conditions and rejects negative, non-finite or invalid decimal amounts.

Keep variable usage, prepaid top-ups, annual/multi-month payments, amortized equivalents, waived historical invoices and unknown amounts outside this subtotal. A fixed base component of a usage plan must not make the whole plan look like a fixed monthly total. Display its basis separately unless the report explicitly models that component without double-counting. Do not sum different currencies or add a points balance to money. Label any equivalent as an estimate and retain the original payment period.

### Evidence and drafts

Each evidence entry uses:

- `date`: the source/event date, with timezone when timing matters.
- `label`: a recognizable source title or short description.
- `note`: the fact it supports and any identity/state limitation.
- `url`, optional: an authorized mailbox display link or official source. The template permits HTTP, HTTPS and mailto links. Local source locators may be kept in additional JSON fields or the note; filesystem links are not rendered as clickable evidence URLs.

Keep unique source IDs and local paths in additional fields where useful. Refer to preserved evidence rather than copying entire messages into the dashboard. Omit raw access tokens and unnecessary payment/account identifiers.

Each draft uses `title`, `condition` and `text` strings. `condition` states the facts to verify before use and whether the action is conditional. The template presents readonly, copyable text. Only include drafts whose assumptions still fit the latest evidence; show obsolete drafts as superseded in the case record rather than as ready-to-use actions. A draft or official link never proves submission.

## Computed fields and verification

The renderer replaces any supplied `computed` value with:

- `service_count`: number of subscription rows, including uncertain/historical rows when present.
- `observed_count`: rows with status `observed`.
- `uncertain_count`: rows with status `uncertain` or `user_reported`.
- `action_count`: subscription rows with truthy `needs_action`; non-subscription cases are excluded.
- `refund_count`: rows classified as `refund` across `subscriptions` and `other_cases`; this is a count of review questions, not approved refunds.
- `other_issue_count`: rows classified as `other` across both arrays.
- `known_monthly`: per-currency totals from explicitly opted-in fixed monthly rows.
- `monthly_includes`: names of the counted rows, shown alongside the subtotal.

The JSON input does not need a `computed` field. Rendering checks subscription structure, unique nonempty IDs across services and other cases, the counted amount constraints and review-group values. Refund rows must be actionable, contain evidence and have valid required `refund_review` fields. These structural checks do not validate every display field, source freshness, truthful classification or refund eligibility. Those remain evidence-review responsibilities.

Before delivery, compare the page with the canonical inventory: all three sections are visible, empty sections say so, user-named services are present, latest events supersede obsolete findings, refund questions have a supported basis, fixed monthly components are the intended subset, non-subscription receipts are separate, and unknowns remain visible. Check representative details and drafts in the rendered data, evidence destinations and that the document has no automatic remote-resource loads. Follow the host's verification rules for browser interaction testing. Deliver the local web document first, with JSON/CSV and supporting report links as needed.
