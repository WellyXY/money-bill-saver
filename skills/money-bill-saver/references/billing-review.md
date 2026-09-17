# Common bill and refund review

Apply this workflow across merchants. A merchant playbook adds detail; it is never an allowlist. Cover every bill discovered within the authorized source/date/account scope and state what could not be read or verified. “All bills” means that documented coverage, not proof that every service the user ever bought has been discovered.

## 1. Find and classify billing evidence

For a mailbox review, start with [email-search-checklist.md](email-search-checklist.md): select the account/date scope, find bills through focused channel queries, then check relevant sender/account/thread events before status/date conclusions. Broader discovery is a separate user-requested follow-up.
The checklist owns query examples, noise reduction and pagination handling. Use host-supported search syntax and record results under [audit-evidence-contract.md](audit-evidence-contract.md).
Keep user-named services even without receipts; incomplete collection leaves affected conclusions provisional. For file-only work, state the supplied document scope instead of implying a mailbox search.

For multipart email, inspect whether the plain-text part contains meaningful content before dropping an HTML alternative. Empty text, “view in browser” and “HTML not supported” fallbacks require reading the HTML part; preserve its source identity and original content. Before reporting an unreadable message or missing amount, check available body alternatives and attachments. A truncated attachment preview is not a complete read: use the complete extraction or original file and inspect relevant pages. If an attachment download fails, use an available authorized alternative such as the original message's MIME attachment; record remaining failures rather than treating the document as absent.

### Retrieve and review attachments

1. Inspect the actual single-message, thread and attachment tools. A thread reader's lack of raw support does not establish the single-message reader's capabilities. Select the target message using its returned message ID, and record the connected mailbox and scope. Use a complete attachment response or full MIME content when available. If retrieval fails or content is missing, try the single-message raw option when supported (for the Gmail tool exposing it, `read_email` with `format: "raw"`). Follow the current tool schema rather than inventing a tool name or format for another host.
2. Retrieve raw content only for relevant or suspected billing/lifecycle messages that need it; some messages cannot be classified until their attachments are read. Preserve the exact tool result locally. When a tool supplies a preview plus a complete saved result, retrieve that complete file through the host's file/resource tools. A file link is not necessarily a local path. If the content itself is truncated and no complete result is available, keep the retrieval incomplete. Avoid copying encoded attachment data into the conversation.
3. Run `scripts/extract_mime.py <local RAW JSON or .eml> --output-dir <fresh directory> --extract-pdf`. Gmail RAW JSON can be direct or wrapped in `structuredContent`; other response envelopes must first be retrieved or adapted without discarding the original. The helper decodes the outer base64url message, parses its MIME structure, saves the exact input and each attachment, and prepares text where supported. Structural MIME or transfer-encoding failures require obtaining a complete source; a successful parse alone cannot establish that a truncated tool result is complete.
4. Read `body.txt`, attachment text and PDF pages, preserving table rows and column relationships from the originals. Inspect every relevant image, including inline images with a Content-ID, and check attached `.eml` messages and their contents. Inspect decoding warnings and PDF page integrity metadata. If text is unreliable, cross-check the original or use authorized visual/OCR capabilities; keep unresolved fields unknown. An encrypted PDF blocks that attachment, while other documents can still be reviewed. Request an unlocked copy when needed.
5. Add the helper's source entries to `audit-evidence.json` as described in [audit-evidence-contract.md](audit-evidence-contract.md). Keep entries `unread` until their actual contents have been reviewed. A known logo may be marked `irrelevant` with its specific reason; unsupported formats remain visible and unresolved when relevant. Record attempted retrieval tools/formats, failure reasons and the affected conclusion before marking a source `inaccessible`.
6. When the available authorized attachment, full-message and raw routes cannot supply the evidence, request a chat upload or connected folder, or use an authorized browser session. State the source gap and retain provisional status until it is resolved.

Attachments can be PDFs, HTML invoices or CSV exports. HTML may declare Big5 in MIME headers or its own markup. Preserve original bytes, identifiers and amounts; a successful fallback decode is not enough to establish that its text is correct. Keep the generated evidence bundle together when moving it. Use a separate output directory; replacing outputs must preserve all input documents.

### Classify documents and reconcile account state

Classify documents before arithmetic:

| Document | Role | Avoid |
|---|---|---|
| Invoice or final bill | Amount billed, line items and service periods; any explicit payment details | Treating issuance alone as settlement or ignoring a paid status/date printed on the same document |
| Paid receipt / payment record | Evidence of a specific payment and its status | Counting the associated invoice again as another payment |
| Estimate / upcoming renewal / quote | Expected future amount or renewal | Including it in incurred bills or paid spend |
| Failed payment / authorization hold | Payment attempt/status | Calling it an additional settled payment |
| Credit note / refund confirmation | Adjustment or refund decision to match to the original charge | Counting a note and later cash movement as two recoveries |
| Cancellation / plan / trial confirmation | Agreed plan, timing and effective state | Assuming it applies to every account or stops already incurred usage |
| Reimbursement / incoming transfer status | Money payable to the user and its processing state | Treating it as subscription spend or a refund of a user-paid subscription |

Normalize invoices into `facts.json`. Keep other evidence in `cases.json` or a sourced case note using the facts contract. A receipt can supplement the same canonical invoice; if it establishes only a payment, keep it as payment evidence. Standalone credits and quotes are not new payable invoices. Use `other` for a line kind that has no dedicated enum, preserving its printed label and explanation. Use `recurring: false` and `cycle: one_time` for a confirmed one-time purchase; omit subscription data when none exists.

Classify payment from the document's content, not its title or the existence of a separate receipt email. An invoice marked paid with an explicit payment date, a merchant confirmation or a transaction ledger can establish the corresponding payment. A successful payment with no date leaves the date unknown while retaining its known paid status. “Will be charged,” an invoice due date and a zero balance alone do not prove a successful cash charge; zero can result from credits or a waiver. Explain which evidence is known rather than reducing every incomplete record to a generic Unknown.

Match merchant, actual seller, payment processor, account, invoice, transaction, billing period and currency. The merchant of record or app store may own the refund channel. Preserve separate accounts and currencies. Stable local aliases reduce exposure in reports; keep original references privately for a draft when needed.

For each apparent failure, cancellation or missing benefit, search later messages from the same merchant and relevant thread before deciding the current state. Match the account and transaction/claim identity, not just the amount or merchant. If later evidence shows payment, reissue, reinstatement or a plan change for the same event, update the latest-state finding and retire contradicted drafts while preserving the dated timeline. A matching application date without a unique claim ID can support a labeled timeline inference, not certain identity. Merchant-marked paid and bank-verified receipt remain separate states.

Keep trial end, paid service start, first billing date, invoice issue date and payment date distinct. If a notice's prose and table disagree, retain both dated statements as conflicting evidence instead of selecting one silently. Request the ledger from the earliest plausible paid-service date so a later first billing date does not hide an earlier charge period.

Track separate promised benefits within a merchant's history: a free service period, replacement coupon and later credit grant may have different redemption status or expiry. Link a replacement to its earlier promise when supported; do not assume that a newer grant fulfilled every earlier benefit or count replacements twice.

Build the current service list from dated state evidence: a paid period covering the audit date, a recent usage signal, an announced renewal or a currently valid entitlement. Describe the specific basis and what has not been checked. Historical receipts alone leave current status unresolved; auto-renew disabled can coexist with a valid prepaid term. Keep historical payment totals, current plan price and remaining credit balance in separate fields.

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

### Proactive screening before a refund case exists

For manage/both audits, check every inventory row for these leads and highlight supported leads before all eligibility evidence is available. Retain the reason, reviewed-source boundary and concrete next check in `review_signals` as defined in `dashboard-contract.md`. Keep these leads separate from specific refund cases and monetary totals.

| Signal | What justifies highlighting it | Next evidence and decision |
|---|---|---|
| Functional overlap | Two discovered services plausibly serve the same user job, or the user reports duplication | Identify both services and ask which workflows, required features and recent tasks each supports. Verify current paid plans and dependencies. Retain both when their roles differ; assess future savings when a viable exit is established. Overlap alone does not establish a refund basis. |
| Use not established | A supported paid term has no supplied activity evidence, an attributed user concern suggests disuse, or available historical service records leave a material current-use gap | State the paid term or last relevant record, the reviewed date/source coverage and what is unknown. Check recent account usage, the user's last use, team activity and running resources; then match any unwanted period to actual charges. |
| Trial conversion unresolved | An account-specific trial notice announces conversion, but later payment/status is unresolved | Check cancellation, post-trial invoices/receipts and current plan before claiming any charge. If a paid conversion is evidenced, establish intent, activity and relevant terms for a refund or courtesy assessment. |

“No updates” needs qualification. Product release announcements or newsletters do not establish account usage. No such emails, no telemetry connection or no activity in selected documents does not prove non-use, current paid status, recurring charges or refund entitlement. Describe a gap in the **available reviewed records** unless an actual scoped search establishes mailbox absence; even scoped mailbox absence is only a weak usage signal. Name relevant coverage limits and do not extrapolate a historical payment into continued monthly charges.

Time-based screening thresholds are configurable review heuristics. A 30-, 60- or 90-day activity window can structure a question when appropriate to the service; record the chosen window and why it helps. It is not a universal inactivity definition or a refund deadline. Running storage, background jobs, occasional critical workflows and reserved phone numbers can remain valuable with few visible interactions.

## 3. Establish use and refund basis separately

Record a charged-period activity observation as service-evidenced, user-reported or unknown, with its date range. An empty mailbox, no app telemetry connection, or missing login events does not prove non-use. Non-use reported by the user can be stated honestly in a request without presenting it as a vendor-confirmed fact. Check background processing, stored data, team members and production dependencies before recommending termination.

Move a screening lead into a specific refund assessment only when a concrete concern is attributable to a payment, billed period or merchant action. For example, a receipt plus the user's dated report that they did not use an unwanted renewed period can support an **unverified** or **goodwill** review; it still does not prove entitlement. A matching cancellation receipt and subsequent inconsistent charged period can support a billing-discrepancy review. Missing usage alone calls for an activity check. An overlap decision with no past-charge concern calls for future cancellation/downgrade, not a retroactive refund claim. A processed refund with no matched bank credit calls for tracing that existing refund, not requesting it again.

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
