# Email search checklist

Start with transaction channels, identify bills and services, then check related account events that could change a conclusion. Run separately for each selected mailbox. Automatic collection stays focused on billing and relevant account events; broader discovery is reserved for a user-requested follow-up.

## 1. Fix the account and time window

- [ ] Record `<MAILBOX_ACCOUNT>`, authorized folders, start/end dates and timezone. Select that account through the connector or Gmail account selector. `to:<YOUR_ALIAS>` filters recipients; it does not select a mailbox and can miss forwarded or differently addressed receipts.
- [ ] Inspect query, paging and message-read fields. Translate these [Gmail operators](https://support.google.com/mail/answer/7190?hl=en) to supported fields on other hosts; record lost coverage.
- [ ] Replace `<DATES>` in every example with `after:<START_YYYY/MM/DD> before:<END_EXCLUSIVE_YYYY/MM/DD>`. Replace all remaining placeholders; none is literal Gmail syntax.
- [ ] Set the exclusive end to the day after the last covered date: September 1–30 uses `after:2026/09/01 before:2026/10/01`. For the Gmail API, date literals mean midnight PST; use epoch seconds when exact timezone bounds matter and the host supports them. Check boundary-message timestamps. See [API filtering](https://developers.google.com/workspace/gmail/api/guides/filtering).
- [ ] Use the user's dates; otherwise cover the last six calendar months through the audit date in the selected timezone. For September 16, start March 16; clamp to the last valid day when needed. Record the actual bounds. Annual plans with no notice in this period may be absent; state this limitation without automatically extending the period. Honor an explicit longer-period request. Search message dates, then read actual charge, invoice and service-period dates separately.

## 2. Run separate candidate searches

Use `billing` or `lifecycle` for these focused searches. Run the channels relevant to the available host and task; record skips and reasons. There is no mandatory merchant-wide pass afterward.

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

For other mailbox languages, replace or extend the phrase sets using terms actually seen in the records: `月結單`, `應付憑據`, `收據`, `已取消`, `請求書`, `領収書`, `Rechnung`, `facture`. Expand subject-only searches to full-message searches when receipts use unfamiliar subjects.

## 3. Control noise without losing evidence

- [ ] Read result headers/snippets first to identify candidates. Fetch full bodies for relevant or ambiguous messages; fetch raw MIME only for identified messages whose complete content or attachments require it. Follow the attachment procedure in [billing-review.md](billing-review.md).
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
- [ ] Associate searches and results with real `service_ids`. Shared-channel searches cover multiple candidates: triage each returned ID against that declared set as the contract requires. Use focused follow-ups where possible; never invent a merchant or silently omit noisy results to satisfy the gate.

For a shared query associated with already discovered `service-a` and `service-b`, a clearly unrelated promotion can be recorded as below (illustrative IDs). Here `service_ids` names the scope against which it was excluded, not the promotion's merchant. Relevant messages still need full saved content; ambiguous messages stay unread until resolved.

```json
{"id":"gmail:promo-message-id","service_ids":["service-a","service-b"],"kind":"message","disposition":"irrelevant","note":"Sender, subject and snippet identify a generic webinar invitation; no account, payment or lifecycle event for either service."}
```

- [ ] Finish when the chosen channel searches and relevant targeted checks are paged and triaged, material bodies/attachments are read, and report conclusions reflect relevant later events. Each reported service/case needs recorded search coverage, including a focused no-result search for an unsupported user-named service. Invoice/receipt filters are valid coverage; unrestricted merchant searches are not required.
- [ ] Preserve explicit unknowns and the period boundary. Missing activity, price or older annual-plan evidence is not a reason to invent values or expand the search. Material unread/truncated sources and incomplete independent review keep the report provisional under the evidence contract. A checked report describes the declared evidence, not every subscription the user may have.

Primary guidance checked September 16, 2026. Adapt the starting queries to observed senders and languages.
