# Railway billing investigation

Use when an invoice, receipt, usage export, or user report concerns Railway.
Scope: inspect supplied evidence, explain the bill, prepare a support case, and verify outcomes.
Official sources checked **2026-09-16**. Recheck relevant sources when preparing an actionable recommendation.
Current documentation does **not** establish terms for an earlier invoice. Prefer dated invoices, signup/plan-change notices, and applicable historical terms; record unresolved conflicts.

## 1. Establish the account, periods, and evidence

Record the following, using `unknown` for missing values:

| Evidence | Minimum information |
| --- | --- |
| Invoice | Invoice ID, issue date, currency, plan, total, amount due, status, source page |
| Identity | Billed workspace/account; relevant project, environment, and service identifiers |
| Fee lines | Description, amount, units, rate, and each line's service period |
| Adjustments | Included-usage allowance actually applied, tax, other credits, applied balance |
| Payment | Receipt/transaction reference, paid amount/date, partial payments, refunds |
| Usage | Same workspace and period; project/service/resource breakdown; actual vs estimated |
| User expectation | Expected price and its source; cancellation date, prior support promises, desired remedy |

An invoice and its receipt usually describe the same obligation. Link them before counting spend or flagging duplication.
Two payment notices alone do not prove duplicate charges: compare invoice/transaction IDs, amounts, settlement status, and partial-cycle billing.
Keep service periods distinct from invoice, payment, and cancellation dates. Post-cancellation billing may settle earlier usage.
An unknown project is not proof of unauthorized use. Check ownership, workspace transfers, and environments within the evidence supplied.
Complete this step when every asserted amount/identity has a source and missing evidence is named.

## 2. Reconcile the charge before judging it

The current [plans](https://docs.railway.com/pricing/plans) describe Hobby as $5/month including $5 resource usage, with only the excess billed separately. The allowance resets each cycle.
The [billing guide](https://docs.railway.com/pricing/understanding-your-bill) describes invoices combining the coming period's subscription with the previous period's usage overage.
Therefore, “I chose $5 and received a $30+ invoice” establishes an expectation gap; it does not establish a billing error.

For each applicable period, distinguish:

- `gross_usage`: resource charges before the plan allowance.
- `allowance_applied`: actual included-usage discount, which can be less than its maximum.
- `usage_overage`: gross usage minus the applicable allowance, floored at zero.
- Subscription charges for their own periods, other adjustments, and tax.

Use either gross usage minus allowance or already-net overage in the reconciliation; never subtract the same allowance twice.
Reconcile displayed lines to invoice total, then separately reconcile credits/payments to amount due and cash charged.
Preserve an unexplained difference as unresolved. Do not invent tax or adjust an extracted amount to make totals match.
For a stable plan without tax or other adjustments, $30 gross usage with a $5 allowance and $5 next-period fee yields $30 due, not $35. Label this a simplified illustration, never a reconstruction of the user's invoice.

The [project usage guide](https://docs.railway.com/projects/project-usage) says all services across a project's environments contribute to billed usage; deleting a project leaves accrued usage in the cycle total.
Match actual usage to the billed workspace and exact period before attributing a cause. Estimated current spend cannot explain a finalized older invoice.
Investigate resource categories shown by the evidence; possible causes include idle services, extra environments/replicas, or public-network database traffic. Keep each cause a hypothesis until supported.
Complete this step with a reproducible reconciliation or the exact missing lines/period data needed to finish it.

## 3. Make three separate decisions

| Decision | Allowed conclusion |
| --- | --- |
| Explainability | Explained, partly explained, or unexplained; cite the amounts and periods supporting it |
| Correction/refund basis | Evidence of a duplicate settled charge, unapplied promised credit, incorrect line, or other specific discrepancy; otherwise `not established` |
| Goodwill request | An honest request for discretionary relief based on the user's stated experience; no claim of entitlement or predicted success |

Correct arithmetic does not establish that every charge is authorized or that historical terms were clear.
An unexplained line does not establish misconduct. Request itemization or clarification while preserving the open question.
An unusual spend increase can support an optimization recommendation even when the invoice is correct.
For cancellation, identify production dependencies, data consequences, and remaining accrued charges before recommending an action.

The current [refund policy](https://docs.railway.com/pricing/refunds) describes discretionary refunds, a Billing History refund control, and resource usage as generally nonrefundable.
It also treats absence of the refund control as ineligibility. Record the observed eligibility and policy checked date; do not promise a support request will override it.
A legitimate discrepancy can still be described factually. Present goodwill separately and respect an explicit denial; never invent non-use, a prior promise, or a qualifying circumstance.
The policy notes that a refund may cancel the subscription and take services offline. Include this consequence when the proposed remedy could affect running services.
Complete this step with three explicit conclusions, supporting evidence, and the next useful action.

## 4. Prepare the appropriate support case

[Railway support](https://docs.railway.com/platform/support) routes ordinary support through [Central Station](https://station.railway.com/), not email. Verify the available billing/refund entry point for the user's plan.
Produce a portal-ready title and body plus an attachment checklist. Use an email draft only when a verified case-specific channel calls for it.
Determine whether the destination is public or private before including invoice/account details; provide a redacted public version if needed.
Stage 0 ends at preparation: label the case `draft_prepared`. A draft, opened page, or copied text is not a submitted request.

Draft pattern (adapt to supported facts; remove unused placeholders):

> Title: Review of invoice [invoice ID] for [billing period]
>
> My workspace is [identifier]. Invoice [ID], dated [date], shows [currency/amount].
> I expected [amount and reason]. My review identifies [verified fee breakdown].
> Please clarify [specific unresolved line, period, allowance, or payment discrepancy].
> [If supported: Please correct [specific discrepancy] and confirm the adjustment.]
> [If appropriate: I understand usage charges may be valid. Given [truthful circumstances], would you consider a one-time refund or account credit?]
> Please confirm the amount, whether it is a refund or credit, and any effect on my subscription or running services before applying a remedy with those effects.
> Relevant evidence: [redacted invoice / matching usage export / earlier support promise].

Attach only evidence needed for this case. Keep credentials, full payment details, unrelated mail, and application logs containing secrets out of the packet.
Complete this step when the request is understandable without the audit conversation, its factual claims are sourced, and the channel and requested remedy are explicit.

## 5. Suggest prevention and verify results

The [cost-control guide](https://docs.railway.com/pricing/cost-control) distinguishes email alerts from hard limits. Compute and Railway Agent spend have separate limits.
A compute hard limit takes workloads offline; an agent limit disables agent usage. Explain the chosen target and operational impact.
Recommend a user-selected alert/cap and review any dependencies; never apply limits, cancel, delete, or redeploy as part of this audit.
A usage cap does not establish an exact ceiling on the final invoice: inspect its covered categories, base fees, tax, and any continuing storage charges.
The [bucket billing guide](https://docs.railway.com/storage-buckets/billing) specifically says stored data remains billable when hard-limit suspension blocks bucket access.

On supplied follow-up evidence, record submission, merchant acknowledgment, remedy approval, and actual settlement as distinct events.
Record cash refunds only when refund/payment evidence supports the amount and currency. Keep an approved-but-unsettled refund pending.
Record issued account credit separately from cash, and subsequently track credit consumption without counting it as a second recovery.
An unpaid invoice waiver reduces a liability; it is not cash returned. A promised credit is not an issued credit.
Verify cancellation with confirmation/effective date, and reconcile any final usage bill. Verify prevention against saved settings or the next relevant invoice.
Separate newly obtained outcomes from refunds the user had already secured before the audit. Future savings remain estimates until observed.

## Optional authorized reads

Start with supplied screenshots/exports and existing authorized read tools. An installed CLI or existing login alone does not authorize account inspection.
When the user has authorized Railway usage reads for this audit, reuse that authorization within its workspace/period scope; inspect local command help before using an available CLI.
Use only usage summaries, project/service breakdowns, or limit status. Explicitly select the verified workspace and requested period. Do not read credential stores, environment variables, service secrets, or authentication files.
The current [CLI usage reference](https://docs.railway.com/cli/usage) supports `current`, `previous`, and `YYYY-MM` periods and documents a 90-day history window; verify the actual installed version's capabilities.
Historical requests beyond available coverage need older exports/invoices. Record `unavailable`, not zero usage.
Limit status describes current settings and cannot prove a cap existed when an older charge accrued.
CLI failure, unavailable history, or missing access leaves manual evidence collection available; it is not a billing verdict.
