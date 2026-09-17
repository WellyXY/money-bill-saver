# Local facts contract (v0.1)

Use this contract after reading selected invoices. It describes a local working file, not a cloud upload format. `check_facts.py` checks invoice arithmetic and document identity; Codex supplies extraction, interpretation, subscription decisions and drafts.

Before transcribing extracted PDFs, inspect each page's manifest integrity metadata. `unexpected_control_character_count` and `unexpected_control_characters` identify Unicode control characters other than normal tab, newline, carriage return and form feed; affected pages have `needs_visual_review: true` and the reason `unexpected_control_characters`. The helper preserves the extracted text, including NULs and other suspicious characters. Cross-check affected identifiers, amounts and other fields against the original PDF or matching authoritative evidence. Never guess that a NUL represents a hyphen, silently discard it, or use a malformed identifier to establish document identity; leave unresolved fields unknown.

## Shape

```json
{
  "schema_version": "0.1",
  "scope": {
    "description": "Selected invoice PDFs; usage supplied manually",
    "start": "2026-07-01",
    "end": "2026-09-01",
    "limitations": ["No bank transactions or service activity connected"]
  },
  "sources": [
    {"id": "src-1", "type": "pdf", "locator": "invoices/example.pdf#page=1"}
  ],
  "invoices": [
    {
      "record_id": "inv-observation-1",
      "vendor": "example-cloud",
      "account_ref": "account-local-a",
      "invoice_ref": "invoice-local-a",
      "subscription_ref": "subscription-local-a",
      "issued_on": "2026-08-01",
      "currency": "USD",
      "amount_due": "32.40",
      "line_items_complete": true,
      "source_refs": ["src-1"],
      "line_items": [
        {"label": "Starter plan", "kind": "base", "amount": "5.00", "period": {"start": "2026-08-01", "end": "2026-09-01"}},
        {"label": "Resources", "kind": "usage_gross", "amount": "30.00", "period": {"start": "2026-07-01", "end": "2026-08-01"}},
        {"label": "Included usage", "kind": "included_usage", "amount": "-5.00"},
        {"label": "Tax", "kind": "tax", "amount": "2.40"}
      ],
      "subscription": {
        "plan": "Starter",
        "cycle": "monthly",
        "recurring": true,
        "renews_on": null,
        "owner": null,
        "activity": "unknown",
        "dependency": "unknown"
      }
    }
  ]
}
```

The example and all packaged sample amounts are synthetic. Do not infer an actual user's invoice, tax rate or account state from them.

## Required semantics

- Required root fields: `schema_version`, `scope` (object), `sources` (array), `invoices` (array). Version must be `0.1`.
- Source IDs and record IDs must be unique, nonempty strings. A source needs `id`, `type` and `locator`; allowed types: `pdf`, `email`, `usage`, `policy`, `user_statement`, `receipt`, `other`. Locators identify supplied local files/pages, messages or authoritative public pages. Never put credentials in them. The checker does not dereference locators or open URLs.
- Every invoice requires the fields through `line_items` shown above; `subscription` is optional. `account_ref`, `invoice_ref`, `subscription_ref` and `issued_on` may be null. Known references must be nonempty strings. Omit actual invoice IDs from shareable output: use stable random local aliases and retain the original mapping locally only if needed. Reuse an alias only when identity has been confirmed from the source.
- Monetary inputs are signed decimal **strings**, e.g. `"32.40"`, or null for unknown. No binary floats, exponent notation, thousands separators, currency signs, NaN or infinity. Preserve currency precision; do not assume two decimals for every currency. Currency is a three-letter uppercase code. Never add different currencies together.
- `amount_due` is the stated payable amount after the represented fees, taxes, discounts, credits and carry-forward adjustments. It is not proof of a successful payment. Record payment/refund evidence separately in the outcome ledger.
- Each line item requires `label`, `kind`, `amount`. `period` is optional, with ISO date `start`/`end` or null for unknown. End must follow start when both are known. Keep source interval boundaries; do not manufacture a month or date. Optional `source_refs` points to supporting sources; otherwise inherit the invoice sources.
- Kinds: `base`, `usage_gross`, `usage_overage`, `seat`, `tax`, `discount`, `included_usage`, `credit_applied`, `carry_forward`, `other`. Use the sign actually printed: fees are usually positive, reductions negative. `usage_overage` already excludes included usage. A mix of `usage_overage` and `included_usage` needs manual review; never silently subtract the allowance twice. Mixed gross and overage may also need review.
- `line_items_complete` is true only when all contributors to `amount_due` were observed. Null fields remain unknown, never zero. The arithmetic delta is `amount_due - sum(known line amounts)`; with incomplete evidence it is an **unexplained residual**, not an overcharge. Even a zero delta is not proof that the merchant's pricing is correct.
- Source refs are nonempty lists of existing source IDs. Quantities, unit prices and usage exports may remain in a separately sourced evidence note for v0.1; the checker does not validate metering, refund eligibility or policy validity.
- Optional subscription data records observations, not guesses. Allowed cycles: `monthly`, `quarterly`, `annual`, `usage`, `one_time`, `unknown`. `recurring` is true, false or null. `activity`: `active`, `inactive_confirmed`, `unknown`; `dependency`: `critical`, `noncritical_confirmed`, `unknown`. Owner/renewal may be null. Explain the evidence for confirmed activity/dependency in the case note. Never infer inactivity from a missing signal.

## Cross-merchant case evidence (maintained by Codex)

The arithmetic schema is merchant-agnostic. A one-time invoice may use null `subscription_ref`, `cycle: one_time` and `recurring: false`. Quotes, pending authorizations, payment-only records and standalone credit notes belong in case evidence rather than being forced into new payable invoices. A negative printed invoice balance is an adjustment balance, not verified cash received.

Use a sourced case note or `cases.json` for the following evidence. These fields are maintained by the agent; `check_facts.py` does not validate them or implement a refund-eligibility engine.

- Stable `case_id`, merchant, seller/payment channel, account reference, invoice record references and document kinds.
- Payment observations: local transaction reference, date, amount, currency, state (`settled`, `pending`, `failed`, `refunded`, `unknown`), and sources. Match duplicate candidates by confirmed transaction identity; report unsettled identity as unknown.
- Expected-price or purchased-benefit observation: amount/units/feature, applicable date or service period, source and whether user-reported or documented.
- Activity observations: charged date range, `active`, `inactive_confirmed` or `unknown`, evidence basis (`service_evidence`, `user_report`, `unknown`), sources and dependencies. If non-use is only user-reported, keep normalized subscription activity unknown and preserve the attributed statement here.
- Policy observations: official URL/source, retrieved date, effective version/purchase date, jurisdiction where material, deadline/timezone, known eligibility conditions and unmet/unknown conditions. Missing deadlines remain null, never assumed.
- Finding: billing discrepancy, policy-supported request, goodwill request, benefit restoration, future cost reduction, insufficient evidence or no issue found; include supporting and conflicting sources.
- Requested remedy and amount/currency when supported, impact on service, draft/channel, required follow-up and outcome references. Keep the amount under review distinct from a supported request amount or verified recovery.

Attach sources and distinguish fact, inference and unknown for every material assertion. A policy request, goodwill request and future cancellation can coexist for one bill without becoming multiple recovered benefits.

## Document identity and reconciliation output

The checker groups records only when **vendor + known account_ref + known invoice_ref** agree. Equal amounts or nearby dates do not establish identity. Different accounts stay separate. Equivalent accounting records merge their source refs. Inconsistent observations of the same invoice produce `identity_conflict` and are excluded from totals until resolved; they do not become two payments. Missing identity fields produce separate observations with a coverage warning.

Normalize complementary evidence before running the checker: update the existing canonical record when a new source fills null amounts or adds missing lines, preserving both source references and the history in the case notes. The checker has no automatic partial/full supersession rule; separate records with different completeness or line sets produce `identity_conflict`, even when an agent could resolve them by inspecting the source. Preserve genuine known-value disagreements as competing observations until resolved. Do not discard provenance while updating a record.

For each unique record the checker reports `reconciled`, `mismatch`, `incomplete`, or `identity_conflict`, its known sum, stated amount, delta and sources. `mismatch` means a complete transcription failed arithmetic, not a proven merchant error. It may reflect an extraction mistake. Document totals per currency include only unambiguous reconciled amounts and are labeled **documented amount due**, never paid spend, recovery or estimated savings. Records with unknown invoice identity, mixed gross/overage basis or a possible repeated allowance are excluded from these totals even when their arithmetic reconciles. Unknown subscription identity alone does not exclude an otherwise confirmed invoice. Reports show exclusion reasons and counts.

## Local outcomes (maintained by Codex)

Keep `outcomes.json` separately when handling real cases. Each event needs a local event ID, case/action ID, observation date, type, status, amount/currency if applicable and source references. Reuse the same event ID when updating evidence; do not double count the same benefit.

- Types: `cash_refund`, `credit_granted`, `credit_used`, `liability_waived`, `benefit_restored`, `service_extended`, `renewal_disabled`, `plan_changed`, `cap_changed`, `forecast_savings`, `observed_savings`. Describe a restored feature, allowance or extension and verify its account/effective date; do not invent a cash value for it.
- Distinguish `reported`, `accepted_pending_verification`, `verified` and `rejected`. User statements may be reported evidence; a merchant promise alone cannot verify cash arrival.
- Keep cash, awarded credit, consumed credit, waived unpaid liability, forecast and observed savings separate. A credit awarded and later used is one benefit at two stages. A cancelled unpaid charge is not cash returned.
- Identify historical/pre-existing results and exclude them from newly created product value. Store forecast baseline, covered period and assumptions. A cancelled annual renewal can be verified before its next payment date, while subsequent non-billing remains pending.
- Cases can close as `explained`, `resolved_verified`, `declined`, `withdrawn` or `insufficient_evidence`. None except a supported financial outcome implies recovered money.
