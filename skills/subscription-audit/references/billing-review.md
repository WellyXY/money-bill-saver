# Common bill and refund review

Apply this workflow across merchants. A merchant playbook adds detail; it is never an allowlist. Cover every bill discovered within the authorized source/date/account scope and state what could not be read or verified. “All bills” means that documented coverage, not proof that every service the user ever bought has been discovered.

## 1. Find and classify billing evidence

Prefer the user's selected mailbox invoices when an authorized mailbox read tool is available. Inspect the tool's actual search, pagination, message and attachment capabilities. Search the authorized folders and dates using billing concepts and language variants: invoice, receipt, payment, subscription, renewal, trial, refund, credit note, cancellation, 帳單, 發票, 收據, 扣款, 續訂, 退款. Include known merchant senders and related billing threads. Complete available result pages and report truncation or inaccessible attachments. Never represent a keyword search as exhaustive mailbox coverage.

For multipart email, inspect whether the plain-text part contains meaningful content before dropping an HTML alternative. Empty text, “view in browser” and “HTML not supported” fallbacks require reading the HTML part; preserve its source identity and original content. Before reporting an unreadable message or missing amount, check available body alternatives and attachments.

If no date range was specified for a mailbox-wide request, propose/use a stated last-13-month window within the user's authorized scope to include annual renewals; follow a user request for all history if supported. Local file reviews cover the supplied documents. A missing mailbox connection does not prevent file-based work: request selected exports while reviewing available evidence. Do not silently substitute samples or claim a mailbox scan.

Classify documents before arithmetic:

| Document | Role | Avoid |
|---|---|---|
| Invoice or final bill | Amount billed, line items and service periods | Treating it as a settled transaction |
| Paid receipt / payment record | Evidence of a specific payment and its status | Counting the associated invoice again as another payment |
| Estimate / upcoming renewal / quote | Expected future amount or renewal | Including it in incurred bills or paid spend |
| Failed payment / authorization hold | Payment attempt/status | Calling it an additional settled payment |
| Credit note / refund confirmation | Adjustment or refund decision to match to the original charge | Counting a note and later cash movement as two recoveries |
| Cancellation / plan / trial confirmation | Agreed plan, timing and effective state | Assuming it applies to every account or stops already incurred usage |

Normalize invoices into `facts.json`. Keep other evidence in `cases.json` or a sourced case note using the facts contract. A receipt can supplement the same canonical invoice; if it establishes only a payment, keep it as payment evidence. Standalone credits and quotes are not new payable invoices. Use `other` for a line kind that has no dedicated enum, preserving its printed label and explanation. Use `recurring: false` and `cycle: one_time` for a confirmed one-time purchase; omit subscription data when none exists.

Match merchant, actual seller, payment processor, account, invoice, transaction, billing period and currency. The merchant of record or app store may own the refund channel. Preserve separate accounts and currencies. Stable local aliases reduce exposure in reports; keep original references privately for a draft when needed.

Keep trial end, paid service start, first billing date, invoice issue date and payment date distinct. If a notice's prose and table disagree, retain both dated statements as conflicting evidence instead of selecting one silently. Request the ledger from the earliest plausible paid-service date so a later first billing date does not hide an earlier charge period.

Track separate promised benefits within a merchant's history: a free service period, replacement coupon and later credit grant may have different redemption status or expiry. Link a replacement to its earlier promise when supported; do not assume that a newer grant fulfilled every earlier benefit or count replacements twice.

## 2. Check every relevant opportunity

| Situation | Evidence to compare | Result and action |
|---|---|---|
| Higher price / hidden add-on / fee | Purchase-time quote, agreed plan, dated change notice, invoice breakdown | Explain supported fees; question unmatched price/add-on lines; draft correction if evidence supports it |
| Usage, seats or quantity too high | Units, rate, allowance, proration, billing window and service export | Recalculate with sourced units; request missing metering or seat history; do not assume a advertised base fee caps usage |
| Possible duplicate charge | Distinct settled transaction IDs, amount/currency, account, service period and refunds | Exclude duplicate documents, pending holds and failed retries; request investigation when separate settled charges are not yet proven |
| Trial became paid / surprise renewal | Trial opt-in, end/renewal timestamps, timezone, notices, payment, relevant refund window | Assess refund or courtesy request and separately propose disabling the next renewal |
| Billed after cancellation | Cancellation receipt/effective date, invoice's service period and account | Separate earlier usage or final fees from continued renewal; seek reversal of a supported inconsistency |
| Subscription or annual plan unused | Activity for the charged period, user statement, service dependencies, purchase date and refund terms | Assess unused-service refund/courtesy request; evaluate future cancellation/downgrade separately |
| Dormant seats / unused allowance | Seat assignment history, activity and capacity needs | Quantify a supported reduction and investigate applicable past-period adjustments; no assumed retroactive refund |
| Overlapping services | Actual use cases, required features, owner and migration/dependency needs | Ask the user to choose where evidence is insufficient; calculate future savings only with a viable exit |
| Paid benefit absent / service unavailable | Purchased feature or allowance, account status, issue timeline, official entitlement/credit terms | Request activation, restored credit/benefit, extension, correction or a supported refund |
| Tax, FX, annual payment, discount expiry | Tax/fee detail, original and settlement currencies, annual cycle, promotion dates | Explain price changes attributable to these factors; escalate only unresolved or inconsistent items |
| One-time purchase / membership / telecom / utility bill | Order or contract, units/delivery/service dates, prior bills and adjustment terms | Review supported charge and service discrepancies; do not force it into a SaaS cancellation model |

Invoice arithmetic is only one check. A perfectly adding bill may use the wrong rate, duplicate a previously paid service or describe a service the user does not need. A large increase is a review signal; attribute the expected amount and do not label the whole difference refundable by default.

## 3. Establish use and refund basis separately

Record a charged-period activity observation as service-evidenced, user-reported or unknown, with its date range. An empty mailbox, no app telemetry connection, or missing login events does not prove non-use. Non-use reported by the user can be stated honestly in a request without presenting it as a vendor-confirmed fact. Check background processing, stored data, team members and production dependencies before recommending termination.

For each potential remedy, distinguish:

- **Documented billing discrepancy:** a sourced rate/quantity/period/payment inconsistency to investigate or correct.
- **Policy-supported request:** the relevant seller policy, purchase channel, date/window and eligibility evidence support requesting a remedy. State unresolved conditions and do not guarantee approval.
- **Goodwill request:** a valid or not-yet-disproven charge with a credible explanation such as an unwanted renewal and reported non-use. Ask for an exception without asserting an entitlement.
- **Benefit restoration:** a purchased/promised benefit appears missing; identify the benefit and evidence needed to restore it or claim an applicable credit.
- **Future cost reduction:** cancellation, downgrade or seat reduction can avoid an estimated future cost. This is distinct from a past-charge refund.
- **Insufficient evidence / no issue found:** identify the smallest next check or explain the charge; keep the service visible in the audit.

Use official merchant or payment-channel sources to verify the live contact route, current request process and deadlines. For past-charge eligibility, seek the terms applicable at purchase/renewal. If only today's policy is available, record the limitation. Do not invent a universal cancellation period, refund right, success probability or entitlement for non-use. If a legal right is material, verify its jurisdiction and authoritative source before making that claim.

## 4. Prioritize and prepare the right request

For each case, record the amount under review, supported request amount if known, currency, evidence strength, policy/deadline source, user's preference, service impact and next evidence/action. Put documented impending deadlines and strongly evidenced material discrepancies first. Use user priorities when present. Unknown eligibility or amount remains unknown; no speculative probability-weighted recovery headline.

For a follow-up after a promised response window, show the start event, timezone and counting assumption. Unless the source says otherwise, count business days starting the next business day, excluding weekends and applicable known holidays; follow up only after the last included day has ended. If receipt time or holiday rules are unknown, label the date provisional. Check for a reply before using a draft that says the window has elapsed.

Produce a ready-to-send email draft or ready-to-paste in-app support request with the official destination. Include:

1. The exact requested remedy and affected invoice/service period.
2. The charge and expected amount, each tied to evidence; separate payment status.
3. The reason: rate/quantity discrepancy, renewal context, attributed non-use, missing benefit or supported policy condition.
4. Only the timeline and attachments relevant to this case.
5. A precise question for unresolved facts or a clear courtesy request when entitlement is unknown.
6. Whether ongoing service should remain active, based on user intent.

Keep refunds, future renewal cancellation and immediate service termination as separately scoped actions. A refund request does not automatically authorize deleting resources or accepting a restrictive settlement. Draft preparation is the default; follow existing explicit authorization for submission and retain its receipt. See `deliverables.md` for reporting and verification.
