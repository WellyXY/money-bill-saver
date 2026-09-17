# One input for the audit and webpage

Use `audit.json` with `schema_version: "audit-1"` as the normal authoring input. Maintain observations and decisions once; `scripts/build_audit.py` derives the existing invoice facts, checks, presentation rows, dates, monthly estimates, case records and evidence manifest. Do not write a temporary report builder or duplicate all those output formats by hand.

This schema is separate from the established arithmetic `facts.json` version `0.1`. Existing facts/dashboard/evidence tools remain supported. The builder does not read email, decide what an invoice means, assess usage/refund eligibility, retrieve policies or perform independent review.

## Build a proposal

Keep the canonical file, originals and all imports in one private bundle. Resolve `scripts/` against this Skill's directory:

```sh
python scripts/build_audit.py --input /private/audit/audit.json --output-dir /private/audit
```

The command writes `facts.json`, `checks.json`, `dashboard.json`, `audit-evidence.json`, `audit-checks.json` and `dashboard.html`. It writes `cases.json` only for actual case/action/outcome records, and `outcomes.json` only for explicitly classified outcomes. Existing outputs require `--force`; original inputs and imported evidence cannot be overwritten. With `--force`, obsolete optional `audit-1` case/outcome files are removed so earlier outcomes cannot masquerade as current output; unrecognized optional files require manual relocation. A successful build means files were generated; inspect the returned `status` and `audit-checks.json`. The output remains **provisional** until source coverage and genuine independent review pass.

For a runnable synthetic example, copy `assets/example-audit.json` into a fresh private directory as **`audit.json`**, then run the command above. That fixture deliberately cites its own synthetic observations and has no independent review. Its page must remain provisional. Real audits must cite preserved originals, never self-authored interpretations as original evidence.

After reviewing the proposal, use the existing [evidence and independent-review contract](audit-evidence-contract.md), then regenerate checks and render with `--require-checked`. The builder never manufactures a reviewer or a pass. Changes to canonical input require rebuilding and checking affected conclusions; existing review bindings must match the regenerated report and evidence.

## Required structure

| Key | Content |
|---|---|
| `schema_version` | Exactly `audit-1`. |
| `scope` | `mode: mailbox` or `files`, `description`, and ISO-date `as_of`; include selected accounts, period, IANA `timezone` and limitations. Timestamp boundaries use that timezone (UTC when omitted). `audit_kind` defaults to `inventory`; use `targeted` only for an explicitly narrow charge/service task. |
| `entities` | One entry per service/account/subscription or one-time case, with unique `id`, `kind: service` or `case`, `name`, `vendor`, `account_ref` and `decision`. Use `account_ref: null` for unknown identity, retaining a separate stable entity ID. |
| `invoices` | Canonical invoice observations, using `entity_id` and the existing facts line-item fields below. Empty is valid when no invoice exists. |
| `events` | Explicit observed payment, lifecycle and other material events below. Empty is valid. |
| `sources` / `imports` | Existing source records or local inventories. Every source reference must resolve to one unique source. |

The builder adds `scope.workflow_version: "audit-1"`. A mailbox inventory requires the initial generic invoice/receipt discovery plan, using actual saved query IDs:

```json
{
  "search_plan": {
    "schema_version": "1",
    "generic_invoice_receipt": {
      "search_ids": ["generic-page-1"],
      "coverage": "all_categories",
      "note": "Invoice/receipt subject discovery, including the relevant local-language terms, across the selected mailbox categories."
    }
  }
}
```

Place `search_plan` inside `scope`. Its IDs reference actual first pages of `scope: "discovery"` searches with `service_ids: []`, a supported `kind`, exact query and saved raw `result_file`. Every following page and returned ID still needs a disposition. This is a collection requirement, not proof that all subscriptions were discovered. `targeted` mailbox audits instead require focused per-entity search coverage. Files-only examples make no mailbox coverage claim.

Optional root fields: `title`, `intro`, `searches`, `source_updates`, `independent_review_file`. Paths are relative to the file that declares them and must resolve inside the private output bundle. Imports from an existing collection use paths relative to that collection file; the builder rebases them without moving evidence. Keep converted MIME message directories intact.

## Entities and agent decisions

Use `account_ref` as a private stable alias, not a card number or public account identifier. An optional `account_alias` controls its visible label. Names include that alias so two accounts at one merchant remain distinct. Optional `subscription_ref`, `plan` and `category` describe the service. Unknown identity remains unknown in the invoice checker; no automatic merchant/account merging occurs.

`decision` requires:

- `status`: `observed`, `uncertain`, `user_reported` or `historical`. An observed status requires sources. The builder does not infer it from a recent invoice or successful payment.
- `status_label`, `status_note`, and `source_refs`: explicit conclusion and support/contradictions considered. Cite the latest lifecycle evidence, including any undated cancellation/reactivation that could affect the state.
- Optional `unknowns`: array of strings. `review_group`: `none` (default), `other` or `refund`; this determines the action queues. `priority` is optional.
- Optional `issue: {title, summary}` and `action: {summary, steps: []}`. Action steps must be strings. An optional official action `url` and `link_label` are passed through; no link is visited or action submitted.
- For `review_group: refund`, supply `refund_review` with `reason`, `amount_label`, `eligibility` (`unverified`, `policy_supported`, `goodwill`, `refund_pending`), `missing_evidence` and **`source_refs`**. The builder never derives refund eligibility from overlap, missing update emails or an invoice amount.
- Optional `drafts`: each has `title`, `condition`, `text` and **`source_refs`**. These stay local. Optional `review_signals` use the existing [dashboard contract](dashboard-contract.md), including `source_ids` and valid related service IDs.

The builder derives evidence timelines from invoices, events and genuinely associated sources. Entries preserve IDs/source references and supplied HTTP(S) source links. It does not invent Gmail URLs, policy URLs or payment events. Timeline date is the event's actual date, not its email receipt date.

## Invoices

Use the [facts contract](facts-contract.md) fields: `record_id`, `invoice_ref`, `issued_on`, `currency`, `amount_due`, `line_items_complete`, `source_refs` and `line_items`. Add `entity_id`. `vendor` and `account_ref` come from the entity and must not be repeated. `subscription_ref` defaults to the entity value; it may be explicitly null. `issued_on`, invoice identity and unknown amounts may be null as allowed by the facts contract.

Amounts are decimal strings; line items retain credits, discounts and taxes with their printed signs. Complete lines must reconcile to the stated amount. The existing checker continues to report mismatches, incomplete lines and conflicting invoice identities; arithmetic success is not evidence of cash payment or a correct merchant tariff.

An invoice's service-period end is displayed as a related date, never guessed to be the next renewal. Unknown issue dates prevent claiming that an older dated invoice is definitely the latest.

## Events

Each event has a unique `id`, `entity_id`, `type`, `occurred_on`, `note` and `source_refs`. Preserve separate observed events; do not turn receipt arrival time into a payment timestamp.

- `occurred_on`: ISO date or timezone-qualified timestamp for the event; use **null** when it is unknown. With a null event date, supply `observed_on` as the dated source observation/confirmation (for example a clearly labeled email receipt timestamp), not when an agent later downloads the old record. It is never substituted into billing dates.
- Optional `amount` plus `currency` must be a nonnegative decimal string and a three-letter code. `payment_succeeded` means explicitly observed **cash payment**, excluding paid-from-credit invoices, waived balances and zero-dollar settlements.
- Optional `invoice_record_id` must belong to the same entity. Match payment identity from evidence; similar dates/amounts do not establish identity.

Supported types:

| Group | Types and additional fields |
|---|---|
| Payments | `payment_succeeded`, `payment_failed`, `refund_received`. Only the first can establish last charge. |
| Service state | `subscription_cancelled`, `subscription_reactivated`, `plan_changed`, `trial_started`, `trial_ended`. Current status remains an explicit decision. |
| Renewal | `renewal_scheduled` requires explicit `renews_on`; `renewal_disabled` records a known disabled schedule. |
| Period and usage | `service_period` requires `period: {start, end}`; `usage_observed`, `user_statement`. A printed invoice line period need not be duplicated as a separate event. |
| Benefits | `credit_granted`, `credit_used`, `fee_waived`, `benefit_restored`, `service_extended`. |

The latest successful dated payment is used only when no undated successful payment could change which is latest. With undated evidence, the field stays unknown and may show the prior dated record separately. Mixed date-only and timestamp evidence on the same local day establishes only the day, not the latest clock time. Failed attempts/refunds never replace it. A later cancellation/reactivation/plan change invalidates reuse of an older renewal schedule. A same-date reactivation and explicit schedule from the same source can agree; conflicting schedules or an unorderable lifecycle event remain unknown. An expired renewal is never rolled forward by adding a month/year.

Events become outcome records only when they explicitly include `outcome_status` (`reported`, `accepted_pending_verification`, `verified`, `rejected`) and boolean `pre_existing`. Supported outcome types map to cash refund, awarded/used credit, waived liability, restored benefit, service extension, disabled renewal and plan change. A merchant promise alone cannot justify a verified cash refund. The builder does not total those categories into recovered money or estimate savings automatically.

## Cost: declare the basis once

An optional entity `cost` contains `kind`, `include_monthly` (default false), `note`, and either:

1. `amount`, `currency`, `source_refs`; or
2. `invoice_record_id`, which supplies the invoice amount/currency/sources. Use only if that entire invoice actually establishes the selected price; usage/tax-heavy totals do not automatically establish a recurring tariff.

For monthly inclusion add positive integer `months` and an explicit `basis`. Supported included kinds are `fixed_monthly`, `fixed_term`, `base_plus_usage`. Inclusion requires an observed service decision. Top-ups, one-time cases, historical plans and unknown prices cannot enter the baseline. Optional `unknown_note` keeps unknown additional usage visible even when the base fee is counted.

The builder produces both the price label and monthly-cost input; optional `label` can clarify an unusual pricing unit. It divides with exact arithmetic and sums before rounding, keeping currencies separate. A six-month amount becomes a monthly estimate, not a claim that that amount is charged each month. No FX conversion or cash-spending total is guessed. Missing monthly costs remain visible gaps, not zero.

## Import saved collection records

Reuse a previous local source inventory or an `extract_mime.py` manifest:

```json
{
  "imports": [
    {"file": "collection.json"},
    {"file": "mime/manifest.json", "service_ids": ["example-personal"]}
  ],
  "source_updates": [
    {
      "id": "gmail:message-id",
      "disposition": "reviewed",
      "note": "Read the full body and checked issue date; payment not established."
    },
    {
      "id": "gmail:message-id:part-1",
      "disposition": "reviewed",
      "note": "Read the invoice text; amount and credits reconcile, with no extraction anomaly."
    }
  ]
}
```

`collection.json` uses existing `sources` and `searches` arrays; MIME imports use their saved `messages[].evidence_sources`. Every imported disposition is preserved; omitted dispositions become `unread`. Optional import `service_ids` only supplies missing associations for a genuinely specific packet. Do not attach a whole mailbox result set to every entity. References from invoices, events and decisions establish material associations; attachments and their parent keep aligned associations. Global irrelevant candidates may have `service_ids: []` with a specific triage reason.

`source_updates` may change only the explicit disposition/note, true entity associations and display metadata; they cannot rewrite original file paths or MIME attachment identities. Mark each material attachment separately after reading. Imported or extracted content, successful parsing and saved hashes do not constitute review.

An imported inventory cannot duplicate a source ID already declared elsewhere. Import once, then use `source_updates`; preserve the exact IDs. All original files, search pages and MIME extraction inventories remain subject to the existing coverage, containment and integrity checks. Use `prepare_review.py` after building to prepare bounded entity packets; the reviewer still reads original evidence and checks discovery omissions and report-wide costs.
