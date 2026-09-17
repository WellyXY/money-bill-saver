# Visual subscription document contract

New audits author [audit.json](audit-model.md) and use `scripts/build_audit.py` to generate this presentation format. Consult this contract for custom views, migration or renderer maintenance; ordinary runs do not hand-author a second complete report dataset.
Use this contract for `dashboard.json`, then render a private, self-contained `dashboard.html`. It is a presentation model derived from the sourced inventory and cases; it does not replace `facts.json`, `checks.json` or the outcome ledger.

## Three-section presentation

A full audit always shows these sections in order:

1. **Current services:** every row from `subscriptions`, with uncertain/historical states labeled. User-named services remain visible even without a receipt. Provide **Services & dates** and **Monthly cost sheet** tabs for the same inventory, with shared search/review filters; explain their state/date and financial purposes.
2. **Refund questions:** show screening leads in a clearly separate **Worth checking before a refund request** group, followed by **Specific refund cases** from `subscriptions` or `other_cases` classified as `review_group: refund`. A lead needs a usage, overlap or trial check; it is not yet a refund claim. Each refund case has a specific sourced reason, amount under review, eligibility state, missing evidence and next step/draft; inclusion does not mean a refund is guaranteed.
3. **Other issues:** rows from either array classified as `review_group: other`, such as renewal decisions, unknown fees, benefits, reimbursements, usage/dependency checks and source gaps.

Keep explicit empty states for empty sections. Do not use other issues to fill an empty refund section. Inventory visibility is independent of issue grouping: a service remains in the first section even when it also appears in a later section. `priority` can affect emphasis but must not hide classified issues.

Counts describe their denominator: “14 services and leads” means 14 inventory rows, which can include observed, uncertain and historical states; it does not mean 14 confirmed paid subscriptions. `observed` itself can reflect service activity or entitlement rather than a settled charge. The cost sheet retains the same rows, including Unknown monthly costs, while only supported components enter the baseline. Screening badges must remain visible in both views. Tab changes and filters change visible rows only; the monthly baseline still describes the full inventory and must be labeled accordingly.

## Render

Use the fixed renderer. Before delivery, follow the short [webpage preflight](web-design.md), which applies the audit-specific design checks for ordinary runs and routes template changes to the bundled guide. This contract governs financial semantics and data fields.

Resolve the script and input/output paths from the installed skill and task directory:

```text
python scripts/render_dashboard.py --input dashboard.json --output dashboard.html
```

Use absolute paths when running the command. Existing output requires `--force`. The renderer reads `assets/dashboard.html`, embeds the supplied JSON with HTML delimiters escaped, computes selected counts/subtotals and writes a local HTML file with owner-only permissions. It makes no network requests. Opening an explicit evidence or support link navigates to that destination; copying a draft does not submit it.

The template uses embedded CSS/JavaScript and system or self-contained embedded fonts. Keep it self-contained: no remotely loaded fonts, analytics, raw email HTML or tracking images. The interface and report data default to English; use another output language only when explicitly requested. Retain original source quotations and identifiers with translations as needed. Publishing private dashboard data requires separate authorization.

## Evidence completion status

For new audits, follow [audit-evidence-contract.md](audit-evidence-contract.md) and supply `--evidence audit-evidence.json`. Use `--require-checked` when producing a completed report. An absent manifest, unreviewed source, unfinished result page, missing independent review or stale review binding makes the output preliminary. The renderer recomputes `computed.audit_quality`; an input value cannot override it. It rejects final rendering when required checks have not passed.

Keep the quality status visible above the service inventory, with the declared scope and unresolved checks. Source-scoped completion does not convert an unknown charge date, current price or refund condition into a confirmed fact. A report can correctly pass with explicitly unknown facts when source collection and independent review are complete within its declared scope.

## Top-level fields

| Field | Type | Meaning |
|---|---|---|
| `title` | string | User-facing document title |
| `intro` | string | Short description of what the inventory lets the user decide |
| `as_of` | string | Audit date, preferably ISO date; not a claim of live account access |
| `status_boundary` | string | Visible distinction between evidence-supported status and unchecked account state |
| `cost_boundary` | string | Visible limits of the fixed monthly subtotal |
| `cost_sheet_file` | optional string | Local adjacent `.xlsx` file created and verified for this report. Use a simple filename such as `subscription-cost-sheet.xlsx`; omit when no workbook exists. |
| `monthly_cost` | object, optional for legacy inputs | Sourced monthly baseline, period normalization and unresolved cost gaps, as specified below; required for newly authored manage/both audits |
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
| `billing_dates` | object | Required in newly authored service rows: separate last invoice, last charge and next renewal events as below |
| `renewal` | string or null | Optional explanatory context; never parsed to invent a structured billing date |
| `needs_action` | boolean | Whether this row requires a user check or proposed action |
| `review_group` | enum, optional | `refund`, `other` or `none`; determines the issue section as specified below |
| `refund_review` | object | Required structured refund question when `review_group` is `refund` |
| `review_signals` | optional array | Specific screening leads, independent of refund classification and monetary totals; defined below |
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

### Three visible billing dates

Every service row shows **Last invoice**, **Last charge**, and **Next renewal** within Known status, on desktop and mobile. Include `billing_dates` with keys `last_invoice`, `last_charge`, `next_renewal`. Missing legacy fields render as Unknown without inference.

Each event contains:

| Field | Type | Meaning |
|---|---|---|
| `date` | ISO string or null | `YYYY-MM-DD` when only a day is supported; use a timezone-qualified ISO timestamp only when the event time is in the source |
| `status` | enum | `confirmed` or `unknown`; next renewal also permits `estimated` or `not_scheduled` |
| `note` | nonempty string | Event meaning, source precision and remaining uncertainty |
| `sources` | array of strings | Stable source IDs/locators supporting the date or explicitly unscheduled renewal |
| `qualifier` | optional string | Short sourced clarification visible beside the date, such as `Manual renewal; auto-renew off` |
| `related_date` | optional object | `{date, label}` for a distinct source-backed event such as term end, expiry, notice or due date; not a substitute for the requested event |

Confirmed and estimated events require a valid date and nonempty source references. Unknown and not-scheduled events have `date: null`; not-scheduled also requires source evidence. A related date needs an explicit label and the event's source references. Estimates apply only to the next renewal and are visibly marked `Est.`. Never infer a successful payment from an issued invoice, a failed payment attempt or an unpaid-fee waiver.

Last invoice means the issue date of the latest observed invoice, not its due date or the arrival time of an email. Last charge means the latest evidenced successful payment, not the most recent invoice or attempted debit. An invoice can be newer than the last successful charge. If the latest known document lacks its event date, state Unknown and optionally identify a previous explicitly dated event as related context. A receipt/order notification alone must not supply an exact charge timestamp unless it states that timestamp or payment date.

Next renewal is a dated renewal/next-charge event supported by the account or merchant notice. Distinguish it from term end, expiry, trial conversion and a historical inferred billing cadence. If auto-renew is off but a manual renewal date is given, retain the date with a visible manual-renewal `qualifier` and a full explanatory note. If no upcoming renewal is scheduled, use not_scheduled only with evidence; absence of a renewal notice is merely unknown. Do not invent a clock time or timezone for day-only sources.

The details view retains full notes and source references for each event. CSV exports keep separate date, status and note columns; do not combine the three dates into a generic last-activity field.

### Screening leads

During a broad manage/both audit, screen every inventory service for functional overlap, uncertain use and trial conversion. Add `review_signals` only when the available evidence or an attributed user concern gives a concrete reason to check. A generic newsletter or missing usage connection alone does not make every merchant a suspicious paid service. Use an empty array when no specific lead is supported. Legacy inputs without the array receive an empty array; the renderer never mines prose or dates to invent signals.

Each signal has exactly these fields:

| Field | Type | Meaning |
|---|---|---|
| `type` | enum | `functional_overlap`, `usage_unverified` or `trial_conversion` |
| `title` | nonempty string | Short visible check, such as “Compare overlapping writing tools” |
| `reason` | nonempty string | Why this service merits review; separate a plausible inference from established facts |
| `evidence_note` | nonempty string | Available source/date coverage, what it supports and what remains unknown |
| `next_check` | nonempty string | The smallest practical check that advances the decision |
| `related_service_ids` | array of strings | Other inventory service IDs; no self, duplicate or non-service references. At least one is required for functional overlap. |
| `source_ids` | array of strings | Unique stable evidence IDs or locators, including URLs when appropriate. These are references, not paths to fetch. An empty array is allowed for a declared evidence gap; explain its boundary in `evidence_note`. |

The signal object contains no refundable amount, eligibility state or assumed saving. Keep those in the separate financial/case model only after the relevant evidence review. Signals do not automatically change `status`, `needs_action`, `review_group`, dates or baseline inclusion. An unresolved screening lead can coexist with an otherwise normal service or with a distinct existing refund case.

Functional overlap means a possible shared job or workflow, not identical products or proven duplicate subscriptions. Identify the peer, compare actual use and required features, and verify prices and exit dependencies before estimating future savings. `usage_unverified` can flag a paid service with no established recent use, or a long gap in the available reviewed records. State the last supported event and reviewed coverage rather than claiming the whole mailbox was silent or that charges continued throughout the gap. Product-update email is neither account activity nor proof of non-use. `trial_conversion` flags an announced conversion whose paid outcome needs checking; it does not imply that a charge occurred.

Any time threshold is a configurable review heuristic, not a merchant refund window. For example, a 60- or 90-day gap can prioritize an activity check only when its start, end, source coverage and service context are stated. The next check should establish usage for a defined period, background resources/team dependencies and actual payments. Refer to [billing-review.md](billing-review.md) for when a screening lead can become a refund, goodwill or future cost-reduction case.

Show the lead title, its screening status and next check in the Worth checking before a refund request group, with full reasons, coverage and references in details. Preserve separate counts for services worth reviewing, individual signals and specific refund cases. Neither screening count is an approved refund count or an amount recoverable.

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

### Known monthly baseline

For a newly authored manage/both audit, include `monthly_cost` and show a **Known monthly baseline** with its components, as-of date and unresolved gaps. This answers the supported part of current cost. It is a normalized cost estimate, not the user's complete spending or the cash charged this calendar month. Keep the fixed monthly subtotal distinct; it is a different subset and must not be added to this baseline.

```json
{
  "monthly_cost": {
    "as_of": "2030-01-01",
    "items": [
      {
        "service_id": "sample-service",
        "amount": "120.00",
        "currency": "USD",
        "months": 12,
        "basis": "Account-specific prepaid annual term still covers the audit date; USD 120.00 divided by 12 months.",
        "sources": ["synthetic-invoice-1"]
      }
    ],
    "unknowns": [
      {"service_id": "sample-service", "note": "Optional usage charges for the current month are not available."}
    ],
    "note": "Known current cost equivalents only. Payment timing and unresolved costs are separate."
  }
}
```

The example is synthetic. `service_id` must identify a subscription row. `as_of` is a valid ISO date (or a timezone-qualified timestamp where justified), and `note` is a nonempty coverage boundary. Both `items` and `unknowns` are arrays, including when empty.

Each item requires a unique service reference, a nonnegative plain decimal-string `amount`, an uppercase three-letter `currency`, positive integer `months`, a nonempty `basis`, and nonempty `sources` containing stable evidence references. Include only rows with `status: observed` and account-specific current price/term evidence. Historical, uncertain and user-reported rows cannot contribute to the calculation. Being observed alone does not establish a price; evidence review must establish the amount, covered term and applicable account.

Use one item per service to prevent duplicate counting. For a monthly tariff or fixed base, `months` is 1; disclose excluded variable usage. For a current prepaid, annual or multi-month term, retain its full source amount and number of covered months, with taxes/fees described in `basis`. A plan base is a current tariff equivalent, not proof that a cash debit is due this month; explain waivers, credits or prepaid coverage that alter actual payment. Never count a credit top-up and its later usage again as separate recurring costs, extrapolate one usage bill into a fixed fee, or replace an unknown account price with a public list price or zero.

Each `unknowns` entry has a known `service_id` and a nonempty `note` stating the unresolved cost or status evidence. A service may appear in both arrays when its fixed base is known but its usage or add-ons are not. Unknown prices stay outside all monetary sums and remain visible. An empty list is not proof that the audit found every account or charge; retain source coverage separately.

The renderer computes `amount / months`, sums the unrounded equivalents by currency, and rounds each currency total to two decimals using half-up rounding. It also computes a two-decimal display amount for each component; displayed rounded components may differ by a cent from the correctly rounded total. Supplied totals are never trusted. Missing legacy `monthly_cost` produces empty baseline results, without guessing from invoice history or the fixed monthly subtotal.

For actual monthly cash spending, separately reconcile successful payments and received refunds within an explicit calendar period, currencies and source coverage. An invoice amount, renewal estimate, prepaid equivalent or waived fee is not a settled transaction. Do not label the known monthly baseline as actual spend or a guaranteed minimum.

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
- `review_lead_count`: distinct subscription rows with at least one validated screening signal, independent of refund classification.
- `review_signal_count`: total validated signals across subscription rows; a service may have more than one.
- `refund_count`: rows classified as `refund` across `subscriptions` and `other_cases`; this is a count of review questions, not approved refunds.
- `other_issue_count`: rows classified as `other` across both arrays.
- `known_monthly`: per-currency totals from explicitly opted-in fixed monthly rows.
- `monthly_includes`: names of the counted rows, shown alongside the subtotal.
- `monthly_baseline`: per-currency, two-decimal totals normalized from validated `monthly_cost.items`; empty when absent.
- `monthly_baseline_items`: input-order item objects retaining `service_id`, `amount`, `currency`, `months`, `basis` and `sources`, with computed `monthly_amount` added for display.

The JSON input does not need a `computed` field. Rendering checks subscription structure, unique nonempty IDs across services and other cases, the counted amount constraints, signal shape/peer references and review-group values. Refund rows must be actionable, contain evidence and have valid required `refund_review` fields. These structural checks do not validate every display field, source freshness, truthful classification or refund eligibility. Those remain evidence-review responsibilities.

Before delivery, compare the page with the canonical inventory: all three sections are visible, empty sections say so, user-named services are present, latest events supersede obsolete findings, refund questions have a supported basis, fixed monthly components and the normalized baseline have the intended distinct bases, non-subscription receipts are separate, and unknowns remain visible. Check baseline arithmetic, covered terms and current account evidence; do not present the estimate as actual cash payments. Check representative details and drafts in the rendered data, evidence destinations and that the document has no automatic remote-resource loads. Follow the host's verification rules for browser interaction testing. Deliver the local web document first, with JSON/CSV and supporting report links as needed.

### Cost sheet presentation

The monthly summary shows every service in a cost table: price evidence, billing basis, monthly equivalent, inclusion/coverage, screening badges and notes or evidence gaps. Explain that this is the financial view of the same inventory shown under Current services, whose purpose is plan/state and billing dates. Only `computed.monthly_baseline_items` supply counted equivalents; other rows display Unknown. Keep detailed notes available without turning the scan view into long paragraphs. On mobile, preserve readable columns with an accessible horizontal scroll region.

When requested, create a matching private workbook using the host's spreadsheet tools. Keep the original amount, currency and covered months beside the formula-derived equivalent; separate cash charges, historical top-ups, waivers and unknowns. Set `cost_sheet_file` only after the workbook has been saved and checked beside the HTML. The template permits simple `.xlsx` filenames without protocols or directories. Deliver the workbook together with the HTML to preserve its download link. Neither file belongs in a public repository.
