# Subscription Audit

A Codex skill for reviewing bills and subscriptions across merchants, investigating possible overcharges or unused paid services, and preparing support requests with traceable evidence.

**Version: v0.5.0 / Stage 0**

The primary output is a private, self-contained webpage. Reports, interface copy, exports and repository documentation default to **English** unless another output language is explicitly requested.

## What the audit delivers

Every audit webpage contains three sections in this order:

| Section | Contents |
|---|---|
| **Current services** | Every observed or user-named service, its latest supported status, plan, cost basis, last invoice issue date, last successful charge date and next renewal. Missing evidence stays visible. |
| **Refund questions** | Specific concerns about overcharges, duplicate payments, unused paid periods, goodwill requests or pending refunds. Each includes its basis, amount under review, eligibility state, missing evidence and next step. |
| **Other issues** | Renewal decisions, unknown prices, usage checks, missing benefits, reimbursements, dependencies and source gaps. |

Empty sections remain visible. A refund question does not mean a refund has been approved or is guaranteed. Normal and resolved services remain in the inventory.

The document includes source timelines, issue details, official support routes and copyable local drafts where appropriate. Supporting JSON and CSV exports retain the evidence model and invoice checks. The webpage is the primary result; a Markdown report can provide additional detail.

## Review coverage

| Bill or situation | Review focus |
|---|---|
| Software, media, tools and memberships | Fixed prices, annual billing, price changes, expired promotions, non-use and overlapping services |
| Cloud, API, telecom and utilities | Rates, usage, seats, allowances, overages and service periods |
| Trials and automatic renewals | Trial and renewal dates, notices, usage, cancellation history and refund conditions |
| App-store and payment-platform purchases | Merchant of record, transaction status and the applicable refund channel |
| One-time purchases and services | Quote differences, itemization, delivery and correction or refund evidence |
| Missing paid or promised benefits | Feature access, credits, service periods, restoration and compensation conditions |

The common workflow applies across merchants in the supplied evidence. Railway is one optional merchant reference, not the scope of the skill.

Non-use triggers a separate refund assessment. Eligibility depends on the purchase channel, dates, applicable terms and evidence. A clearly attributed goodwill request can be appropriate when entitlement is not established. Cancelling future renewal and requesting a past-charge refund remain separate actions.

## Workflow

1. Discover services from bills, receipts and welcome, plan, trial, renewal and cancellation notices. Keep services named by the user even when no receipt is found.
2. Classify invoices, settled receipts, payment attempts, estimates, credits and incoming reimbursements before calculating totals.
3. Follow later events for the same account and transaction. A newer payment or plan confirmation can change an earlier conclusion while the full timeline remains available.
4. Check invoice arithmetic, identity, service periods, rates, usage and potential duplicate payments. Record evidence gaps explicitly.
5. Assess usage and service dependencies, then prepare a supported correction, refund, benefit-restoration or future-cost decision.
6. Apply the bundled design guidance and render the three-section webpage with evidence, actions and local drafts.
7. Submit requests or change settings only within the user's separate authorization and the host's actual tool capabilities. Preserve receipts and verify outcomes.

## Install and use

Copy this repository's [`skills/subscription-audit`](skills/subscription-audit) directory into your Codex skills directory, usually `~/.codex/skills/`. If `CODEX_HOME` is configured, use its `skills/` directory. Update an existing installation by replacing the same skill directory.

Example request:

```text
Use $subscription-audit to review all bills I supply or authorize you to read.
Investigate possible overcharges, duplicate payments, unused services,
unwanted renewals and missing benefits. Deliver an English offline webpage
with current services, refund questions and other issues, including costs,
evidence gaps, next steps and support drafts.
```

For a mailbox review, specify the account and date range and use an authorized mail tool available in the current environment. This skill does not bundle a Gmail or Outlook connector. Mail exports and invoice attachments also work. Incomplete source coverage is disclosed in the result.

Installing the skill alone does not authorize mailbox scanning. A service tool or existing login does not establish access to its invoices, usage or cancellation features.

## Bundled design guidance

Every audit webpage run must read the integration in [`web-design.md`](skills/subscription-audit/references/web-design.md) and the complete bundled [`design-taste-frontend` skill](skills/subscription-audit/references/design-taste-frontend/SKILL.md). The full design source is included inside this skill; installation does not depend on a separate personal skill path.

The original design skill primarily targets landing pages and explicitly excludes dashboards and data tables. The integration applies its relevant typography, color, spacing, layout, accessibility and preflight guidance to a financial document. Audit evidence, privacy, exhaustive inventory and the three required sections take precedence over marketing-page conventions.

The page uses native CSS and self-contained assets. Light and dark themes, responsive layouts, readable financial data and accessible controls serve the audit. It does not become a conversion page, truncate the inventory to highlights, or require decorative generated imagery. Private bills and mailbox data are not used to generate decorative images.

## Local tools

The tools have been tested with Python 3.12. Invoice checks and webpage rendering use the Python standard library. PDF text extraction uses `pypdf` or an installed Poppler `pdftotext` executable.

Install the tested dependencies in an isolated environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Check the synthetic invoice example:

```sh
mkdir -p work
python skills/subscription-audit/scripts/check_facts.py \
  --input skills/subscription-audit/assets/example-facts.json \
  --output work/example-checks.json
```

Extract a PDF supplied for the audit:

```sh
python skills/subscription-audit/scripts/extract_pdf.py \
  /absolute/path/to/invoice.pdf --output-dir work/extracted
```

Render the synthetic webpage example:

```sh
python skills/subscription-audit/scripts/render_dashboard.py \
  --input skills/subscription-audit/assets/example-dashboard.json \
  --output work/dashboard.html
```

All three tools support `--help`; replacing existing output requires `--force`. The examples are synthetic and do not represent a real account. `work/` is excluded from version control. Keep real bills, messages, account mappings and audit outputs in a private working directory.

## Cost and evidence semantics

- Unknown prices remain unknown, not zero or public list prices.
- Fixed monthly prices, variable usage, prepaid balances, annual or multi-month equivalents and historical invoice totals are separate quantities.
- Fixed monthly subtotals include only source-supported, explicitly selected monthly prices and are separated by currency. They do not represent complete spending.
- A reconciled invoice proves arithmetic consistency, not payment, appropriate metering or refund eligibility.
- Failed payment notices, duplicate documents and pending authorizations do not establish duplicate settled charges.
- An old receipt, a product announcement or absence of a cancellation email does not establish a currently active paid subscription.
- Disabled auto-renew can coexist with a valid prepaid service term.
- Cash refunds, credit awards, waived unpaid bills, restored benefits and estimated savings remain separate outcomes. Historical results do not become newly recovered money.

## Output and privacy

`dashboard.html` contains its data, styles and scripts. System fonts or embedded font data keep the document self-contained. It does not load remote fonts, images, analytics or trackers; evidence and support links are followed only when the user chooses to open them.

Rendering the webpage does not send messages, submit disputes or change accounts. Copying a draft is not submission. Real audit webpages and evidence should remain private and must not be committed to this public repository.

The local helper scripts make no network requests. Evidence read by the assistant may still be processed by the model provider configured in the host; local execution does not imply local-only model processing.

Original source text and identifiers are preserved. English summaries or translations do not replace source evidence. Another report language can be requested explicitly.

## Validation

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests/subscription-audit -p 'test_*.py'
```

The synthetic test suite covers decimal arithmetic, document identity and duplicate observations, incomplete or conflicting records, PDF extraction and damaged-text warnings, varied billing cycles, cross-merchant cases, safe webpage data embedding, monthly subtotal boundaries and issue classification.

Browser and visual checks are separate from these automated tests. Use the host's permitted checks to verify the rendered document and report only checks that were actually performed.

## v0.5.0

- Known status now always shows Last invoice, Last charge and Next renewal on desktop and mobile.
- Each date retains its source, precision and status; unknown dates remain explicit.
- Renewal dates are separate from term end, expiry, manual-renewal requirements and failed payment attempts.
- Existing inputs receive unknown dates rather than dates guessed from free text.

## v0.4.0

- English defaults for reports, interface text, exports, examples and repository documentation, with explicit language overrides.
- A full portable copy of `design-taste-frontend`, required reading for every audit webpage run.
- Audit-specific design integration that preserves the complete financial inventory, three-section structure, private data and offline delivery.
- Refined page presentation with theme, responsive-layout and interaction guidance while retaining the existing evidence and cost boundaries.

## Capability limits

Codex performs reading, source research, usage interpretation and drafting. The helpers extract text, check invoice consistency and render sourced presentation data; they do not independently determine refund eligibility.

Scanned PDFs or complex layouts may require visual inspection or OCR. Extraction warnings identify unexpected control characters and preserve the original text for cross-checking; the helper does not guess missing characters or guarantee that every PDF can be parsed.

Mailbox discovery can be incomplete, and a current service inventory may require account pages, bank statements, app-store receipts or other billing accounts. These gaps must stay visible. The audit does not promise refunds, claim unverified non-use or silently cancel services.

## Reference files

- [Skill entry point](skills/subscription-audit/SKILL.md)
- [Common billing review](skills/subscription-audit/references/billing-review.md)
- [Facts and outcomes contract](skills/subscription-audit/references/facts-contract.md)
- [Deliverables](skills/subscription-audit/references/deliverables.md)
- [Dashboard data contract](skills/subscription-audit/references/dashboard-contract.md)
- [Web design integration](skills/subscription-audit/references/web-design.md)
- [Bundled design skill](skills/subscription-audit/references/design-taste-frontend/SKILL.md)
