# Email search checklist

Start with invoice/receipt subjects across senders and categories, supplement with transaction channels, then check related account events that could change a conclusion. Run separately for each selected mailbox. Automatic collection stays focused on billing and relevant account events within the chosen period.

## 1. Fix the account and time window

- [ ] Record `<MAILBOX_ACCOUNT>`, authorized folders, start/end dates and timezone. Select that account through the connector or Gmail account selector. `to:<YOUR_ALIAS>` filters recipients; it does not select a mailbox and can miss forwarded or differently addressed receipts.
- [ ] Inspect query, paging and message-read fields. Translate these [Gmail operators](https://support.google.com/mail/answer/7190?hl=en) to supported fields on other hosts; record lost coverage.
- [ ] Replace `<DATES>` in every example with `after:<START_YYYY/MM/DD> before:<END_EXCLUSIVE_YYYY/MM/DD>`. Replace all remaining placeholders; none is literal Gmail syntax.
- [ ] Set the exclusive end to the day after the last covered date: September 1–30 uses `after:2026/09/01 before:2026/10/01`. For the Gmail API, date literals mean midnight PST; use epoch seconds when exact timezone bounds matter and the host supports them. Check boundary-message timestamps. See [API filtering](https://developers.google.com/workspace/gmail/api/guides/filtering).
- [ ] Use the user's dates; otherwise cover the last six calendar months through the audit date in the selected timezone. For September 16, start March 16; clamp to the last valid day when needed. Record the actual bounds. Annual plans with no notice in this period may be absent; state this limitation without automatically extending the period. Honor an explicit longer-period request. Search message dates, then read actual charge, invoice and service-period dates separately.

## 2. Run separate candidate searches

Use `billing` or `lifecycle` for these focused searches. A broad mailbox audit requires the generic billing search below; run the additional channels relevant to the host and record skips/reasons. A single-charge task can stay targeted. There is no mandatory merchant-wide pass afterward.

**Generic invoices and receipts — required mailbox discovery, `billing`**

```text
<DATES> {subject:invoice subject:receipt subject:"billing statement" subject:發票 subject:收據 subject:帳單 subject:月結單 subject:應付憑據}
```

Run this across senders and categories, including archived mail within the authorized folders. Invoice mail can be classified as Updates and can come directly from a merchant rather than Stripe. Purchases-category or processor queries do not replace this search. Include relevant mailbox-language equivalents and keep the original executed query. Subject-only terms limit incidental matches in marketing bodies; the channels below cover additional naming patterns. If the host lacks equivalent subject search, use its supported general billing search and describe that substitution. If it cannot search billing evidence at all, record the gap and retain provisional status.

Record the actual first-page search IDs under `scope.search_plan.generic_invoice_receipt` using the versioned [search plan](audit-evidence-contract.md#search-coverage). Mark these shared searches `scope: "discovery"` with `service_ids: []`; this declares a candidate pool, not evidence for every entity. The reviewer checks the exact queries against the declared strategy. A generic query with restrictive sender/category filters does not satisfy this step.

**Purchases category — `billing`**

```text
<DATES> category:purchases
```

Use this category when available. It includes one-time purchases; check sender and merchant passes for absent or misclassified receipts.

**Stripe and known payment senders — `billing`**

```text
<DATES> from:stripe.com
```

Start without English billing keywords so localized Stripe receipts remain discoverable. Read the named seller, product and account; a processor sender does not identify the subscription merchant. Stripe supports [merchant email domains](https://docs.stripe.com/get-started/account/email-domain), so follow observed sender aliases too. Repeat for other known payment senders.

**Apple / App Store — `billing`**

```text
<DATES> {"receipt from Apple" "invoice from Apple" "apple.com/bill"}
<DATES> from:apple.com {receipt invoice subscription renewal}
```

Inspect the app/service and Apple Account on each receipt; map the purchase channel separately from the app's brand. Apple's [receipt-search guidance](https://support.apple.com/en-us/118428) uses those receipt phrases. Check observed sender aliases, localized receipts, another authorized Apple Account or supplied purchase history when needed; an app can also bill directly or through another provider.

**Credit-card charge alerts — `billing`**

```text
<DATES> from:<KNOWN_CARD_ISSUER_SENDER> {"transaction alert" "purchase alert" "card charged" "消費通知" "交易通知"}
```

Use a sender verified from the user's records. If no issuer sender is known, first run the same alert phrase group without `from:` over short date slices to identify senders, then follow up by sender. Extract the merchant descriptor, amount, currency and card/account reference as leads. Read whether the event is pending, an authorization, declined, reversed or posted; an alert alone does not establish a settled charge. Reconcile a relevant alert with the receipt or posted transaction evidence.

**Trial expiry and renewal — `lifecycle`**

```text
<DATES> {"free trial ends" "trial ending" "trial expires" "subscription renews" "upcoming renewal" "試用到期" "自動續訂"}
```

Read the named service, trial deadline and announced price. Confirm whether a charge occurred and whether cancellation or a later plan event supersedes the notice. A reminder is not proof of payment.

For other mailbox languages, replace or extend the phrase sets using terms actually seen in the records: `請求書`, `領収書`, `Rechnung`, `facture`. When an observed or user-named service uses unfamiliar subjects, use a targeted sender/account plus full-message billing query within the same period.

## 3. Control noise without losing evidence

- [ ] Read result headers/snippets first to identify candidates. Fetch full bodies for relevant or ambiguous messages; fetch raw MIME only for identified messages whose complete content or attachments require it. Follow the attachment procedure in [billing-review.md](billing-review.md).
- [ ] Deduplicate overlaps before reading bodies. Within the selected account, reuse saved messages and exact-byte attachment extraction; preserve each search occurrence and attachment association. A duplicate document is not another payment.
- [ ] Group clear promotions for efficient triage, retaining each message ID and a specific reason. Subject keywords alone cannot exclude an ambiguous plan, trial or account notice. Promotions can carry useful account leads.
- [ ] Prefer confirmed senders plus billing/event terms over bare brand words. For shared payment senders, include the observed merchant/account identifier. If a category exclusion prioritizes a pass, record it and use focused sender/event checks for relevant notices that may be misclassified.
- [ ] Follow every page token with the same exact query until it ends. A result estimate or the first 100/200 items is not completion. Gmail's [list API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) returns IDs and paging metadata; retrieve message content separately when needed.
- [ ] Split future queries by month/week or merchant when the host truncates results. Cover the whole declared interval, overlap uncertain boundary days and deduplicate by mailbox + message ID. Preserve the original query/result; splitting cannot erase an unfinished page chain already recorded in the audit manifest. Unrecoverable truncation stays provisional.

## 4. Check related account events

Before a current-status, renewal or unresolved-payment conclusion, check relevant events within the selected period using confirmed sender/account identifiers or the related thread. Follow a cancellation, failure or promised refund through later messages for that same event. Adapt event words to the source language:

```text
<DATES> {from:<KNOWN_SENDER> from:<KNOWN_SENDER_ALIAS>} {cancelled canceled refund refunded renewal "plan changed" "payment failed" "trial ends" 已取消 退款 續訂 付款失敗}
```

The sender group and event group are combined with AND; keep brand words out of the sender OR group. Select relevant terms, such as upgrade, downgrade, credit, reinstatement or resource deletion, for the actual service and question. A complete related thread can supply these events without another search. A dated invoice alone cannot establish that auto-renewal is enabled.

For shared platforms, include the observed app/product/account identifier; a Stripe/Apple domain alone does not identify a merchant. Include known aliases explicitly: Gmail API searches do not expand aliases or match whole threads like the Gmail UI does. See [API differences](https://developers.google.com/workspace/gmail/api/guides/filtering).

For a user-named service missing from channel results, run a focused service + billing/event query in the same period. Keep an unresolved inventory row if no supporting record is found. Missing receipts or conflicting evidence produce a stated gap and a concrete follow-up; they do not automatically trigger unrestricted brand searches or a longer date range. Broader discovery can be performed when the user requests that investigation.

Add `in:anywhere` only when Spam and Trash are authorized; otherwise state the excluded folders. Keep absence claims specific: “No receipt found in these searches during this period,” not “No subscription exists.”

## 5. Record and finish

- [ ] Preserve exact executed queries, selected account/window/folders, raw result pages, request/next tokens and source IDs under [audit-evidence-contract.md](audit-evidence-contract.md). Use `result_file` for searches and `file` for sources.
- [ ] Give every returned ID a disposition and reason: `reviewed`, `irrelevant`, `unread` or `inaccessible`. An irrelevant result need not have a full download; relevant reviewed messages and attachments need saved content. Record attachments separately.
- [ ] Keep discovery coverage separate from service evidence. Shared candidate searches use `scope: "discovery"`, `service_ids: []`. Relevant source entries bind to the actual service/case IDs they concern. Targeted searches bind to those entities; an unsupported user-named service still needs a recorded targeted search, including its zero-result page.

For a global discovery query, a clearly unrelated promotion can be excluded once (illustrative ID). Relevant messages need saved content and their real entity association; ambiguous messages stay unread until resolved. Neither the shared query nor its irrelevant results need to be copied into every service's review packet.

```json
{"id":"gmail:promo-message-id","service_ids":[],"kind":"message","disposition":"irrelevant","note":"Sender, subject and snippet identify a generic webinar invitation; no account, payment or lifecycle event."}
```

- [ ] Finish when the generic invoice/receipt search, applicable channel searches and relevant targeted checks are paged and triaged, material bodies/attachments are read, and conclusions reflect later events. Each reported service/case needs real discovery-source or targeted-search coverage, including a focused no-result search for an unsupported user-named service. An exhausted query list can still have a discovery gap; the reviewer checks query choices and excluded candidates too.
- [ ] Preserve explicit unknowns and the period boundary. Missing activity, price or older annual-plan evidence is not a reason to invent values or expand the search. Material unread/truncated sources and incomplete independent review keep the report provisional under the evidence contract. A checked report describes the declared evidence, not every subscription the user may have.

Primary guidance checked September 16, 2026. Adapt the starting queries to observed senders and languages.
