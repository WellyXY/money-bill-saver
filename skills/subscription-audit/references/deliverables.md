# Reports, drafts and follow-up

Default analysis, web interface, report copy, human-readable exports and support drafts to English unless the user explicitly requests another output language. Preserve original source quotations and identifiers, adding translations where useful. A different merchant submission language should be explicitly requested or presented as a clearly labeled optional translation. Keep actual identifiers in private local case material only where the merchant needs them; use local aliases in the overview.

## Artifact set

For an audit, use a private task-owned directory with:

- `dashboard.html`: the primary, self-contained visual document with three sections in order: current services, refund questions and other issues. Include source timelines, concrete next actions and available drafts in the relevant details.
- `dashboard.json`: the sourced presentation data specified in [dashboard-contract.md](dashboard-contract.md), including `monthly_cost` for manage/both audits. Generate the page with `scripts/render_dashboard.py`; keep unknown status and price visible.
- `facts.json`, `checks.json` and `subscriptions.csv`: the underlying invoice checks and service inventory. The CSV reflects the same services and separate invoice, charge and renewal dates/statuses as the dashboard, without mixing historical invoice sums into current monthly price.
- `cases.json`, local draft files and `outcomes.json` when the task contains cases or tracked outcomes. `audit.md` can provide a longer narrative or working record; it is not the only user-facing result.

A single-charge audit keeps the three web sections scoped to that charge/service. Follow an explicitly requested alternative output format. Avoid producing empty files merely to fill the set. Source PDFs and extraction text are working evidence, not default shareable exports. Creating a private dashboard does not authorize uploading its financial or mailbox data to hosting.

## Visual document

Before producing any audit webpage, read [web-design.md](web-design.md) and the complete bundled [design-taste-frontend skill](design-taste-frontend/SKILL.md). Use the audit integration guidance to apply appropriate design rules while preserving financial evidence and the complete inventory.

Read [dashboard-contract.md](dashboard-contract.md) for the renderer schema and validation boundary. The default audit page presents these three sections in order:

| Section | Contents | Required distinctions |
|---|---|---|
| **Current services** | Every observed continuing service and every service explicitly named by the user; plan, current known state/date, price/cycle, last invoice issue date, last successful charge date, next renewal, issue and next action | Normal/resolved services remain visible. Uncertain or historical evidence is labeled and does not become a claim of current activity. |
| **Refund questions** | Specific, sourced concerns about possible overcharges, duplicate payments, unused paid periods or a refund still being traced | For each item show the reason, amount under review, eligibility state, missing evidence, proposed action and draft when appropriate. Unknown amount stays unknown; an approved historical refund awaiting receipt stays distinct from a new refund opportunity. |
| **Other issues** | Renewal choices, missing price details, benefit restoration, reimbursements, usage/dependencies and source gaps without a specific refund basis | These can be valuable actions without being counted as refundable money. An ordinary reimbursement payable to the user is not a refund of subscription spend. |

Each item opens the supporting timeline, unresolved facts, official action route and copyable draft when one exists. A service remains in the first section when it also has a refund question or other issue. Include non-subscription refund cases in the refund section only when they have a specific sourced refund basis; other non-subscription cases go to other issues. Source type alone does not decide the issue group.

Keep all three headings even when a section has no items, and state that no supported items were found. Do not promote missing cost data, ordinary benefits or unrelated reimbursement questions into refund opportunities to populate the page. A suspicious charge may be unverified; explaining that uncertainty is part of the refund question. The presence of a source does not itself establish refund entitlement.

Make the coverage boundary visible near the list. Label an evidence-supported paid term or recent usage signal precisely; do not relabel every discovered merchant as a currently active subscription. Include a latest-state correction where new evidence changes an earlier finding, and retire any draft contradicted by that evidence. Preserve the original event in the timeline without presenting it as the current problem.

Show only sourced fixed monthly prices in a per-currency monthly subtotal. Display variable usage, prepaid purchases, multi-month/annual equivalents and unknown prices separately. The renderer's computed subtotal is a subset, not the user's complete monthly spending. Historical invoice face values, settled payments, credits and refunds remain distinct quantities.

For manage/both audits, show **Known monthly baseline** near the current-services overview. List its as-of date, each source amount and covered term, monthly equivalent and evidence basis. Use the dashboard contract's validated `monthly_cost` items to combine account-specific current fixed prices or plan bases with equivalents of still-valid prepaid terms, once per service and separately by currency. Explain that this is a cost estimate; actual cash charged this month can differ because of payment schedules, waivers and credits. List unresolved prices, usage and add-ons with the service and evidence needed. Do not add the separate fixed monthly subtotal to this baseline or label the baseline as complete spend, actual payments or a guaranteed minimum. An actual cash-spend view needs a separately reconciled transaction period and sources.

Open the generated page locally and check all three sections against the source inventory and case classifications, including empty states, distinct monthly calculations and their components, unresolved costs, readable details, evidence links and copyable drafts. Priority affects emphasis, not whether a classified item is shown. Keep source text escaped and network-loaded resources out of the document; do not embed raw email HTML, tracking pixels or private invoice access tokens. Default the template and data copy to English; localize them only when the user explicitly requests another output language. Check both light and dark themes, mobile layout, keyboard focus and reduced-motion behavior using the host's permitted verification tools.

## audit.md

Start with the supported finding and the proposed next step. Include:

1. **Coverage:** selected vendors/accounts, source files or messages, observed service periods, missing activity/payment data. State whether the evidence is synthetic, historical or current.
2. **Observed bills and subscriptions** (manage/both): all discovered services and services explicitly named by the user, account alias, document kind, latest supported state/date, last invoice date/time, last successful charge date/time, next renewal date/time, plan/cycle, cost basis/currency, owner, activity with evidence basis, dependency, issue and recommendation. Keep unknown identities separate. Monthly equivalents of annual fixed fees are estimates; a usage invoice is not a recurring fixed plan price. Keep no-issue, resolved and insufficient-evidence entries visible. Put one-time purchases, incoming reimbursements and payment channels in a separate section without inventing subscriptions.
3. **Charge and benefit cases** (recover/both): local case ID; expected price/benefit attributed to its source; stated amount due and payment status; explainability; unused-period evidence; refund basis or goodwill grounds; applicable policy/deadline and seller channel; facts/inferences/unknowns; item-level calculation; dated source links/pages; missing evidence; recommended channel/action. Use the cross-merchant case evidence in `facts-contract.md`. Separate amount under review, requested remedy and confirmed recovery.
4. **Action queue:** action ID, case/subscription ID, action type, exact target, intended change, impact, draft location, official submission route, receipt needed, next check date and current status. Keep local preparation distinct from remote draft creation or submission.
5. **Results:** only when present, supported outcomes grouped as cash refunded, credit granted, credit used, waived unpaid fees, benefits restored, service extensions, estimated savings and observed savings. Do not add categories into a single recovered-money headline. If no action was submitted, state that plainly.

For `subscriptions.csv`, quote values and protect spreadsheet formula prefixes (`=`, `+`, `-`, `@`) in user-controlled text fields. Use separate numeric money and currency columns. Put stable local aliases instead of payment/card/account identifiers in default exports.

## Merchant request

A useful draft contains the request, account/invoice references that the user can supply privately, timeline, observed amounts, supporting explanation, desired remedy and attachments. Use source-backed statements. User-reported expectations can be attributed as such; evidence gaps become questions. Avoid turning a possible extraction error into an accusation.

Choose the supported remedy: itemized explanation, correction, policy-supported refund, unused-service courtesy refund/credit, activation/restoration of a paid benefit, service extension, renewal cancellation, downgrade or confirmation of promised action. Attribute reported non-use and distinguish it from verified activity. Preserve service access when the user requests a refund only. Never combine cancellation with a refund request by default.

If the channel requires an account session or form, provide ready-to-paste text and the verified official entry point. Email is appropriate only when the merchant supports it. Use `[invoice reference]` only where a genuinely missing identifier must be supplied; label that draft as incomplete. Do not invent a ticket number or claim submission.

## Verification plan

| Action | Confirmation evidence | What remains pending |
|---|---|---|
| Refund requested | Submitted message or ticket receipt | Merchant decision and later payment evidence |
| Cash refund | Matched refund transaction/payment evidence | Unmatched partial amount, if any |
| Credit granted | Account credit record or explicit credit note | Restrictions, expiry and later use |
| Benefit restored / service extended | Account feature/allowance or new end date confirmed | Any unmet entitlement, expiry or access condition |
| Renewal cancelled | Renewal disabled with effective date | Non-billing at the expected renewal date |
| Downgrade | Effective plan and date | Comparable next-period charges and service impact |
| Spending cap | Setting value and target confirmed | Whether the user accepts its workload effect |

The case may close as explained, declined or withdrawn without financial success. For disputed outcomes, retain the competing evidence and mark it unresolved. A follow-up date in the report is not a scheduled task. If the user asks for scheduling, use the host's actual scheduling capability and report only confirmed creation.

## Demo discipline

Synthetic inputs must be visibly labeled in the report and result ledger. An example using Railway prices does not validate actual account usage or a tax rate. A historical successful case can test reconstruction; count new product-attributable value only after a new supported outcome.
