# Reports, drafts and follow-up

Use the user's language for analysis. Draft in the merchant's support language when helpful. Keep actual identifiers in private local case material only where the merchant needs them; use local aliases in the overview.

## Artifact set

For a full audit, use a task-owned directory with `audit.md`, `facts.json`, `checks.json`, and `subscriptions.csv` if a tabular inventory helps. For cases, add a draft text file per action and `outcomes.json` when tracking is needed. A single small charge review can stay in the response plus its evidence/checks. Avoid producing empty files merely to fill the set. Source PDFs and extraction text are working evidence, not default shareable exports.

## audit.md

Start with the supported finding and the proposed next step. Include:

1. **Coverage:** selected vendors/accounts, source files or messages, observed service periods, missing activity/payment data. State whether the evidence is synthetic, historical or current.
2. **Observed bills and subscriptions** (manage/both): all discovered vendors within coverage, account alias, document kind, plan/cycle or one-time purchase, billed amount/currency, observed dates, renewal, owner, activity with evidence basis, dependency and recommendation. Keep unknown identities separate. Monthly equivalents of annual fixed fees are estimates; a usage invoice is not a recurring fixed plan price. Keep no-issue and insufficient-evidence entries visible. Label one-time purchases without inventing a subscription.
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
