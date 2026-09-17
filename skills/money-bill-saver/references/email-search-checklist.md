# Email search checklist

When keyword searches return hundreds of newsletters, start with transaction channels, identify merchants, then complete each merchant's lifecycle search before status or absence claims. Run separately for each selected mailbox.

## 1. Fix the account and time window

- [ ] Record `<MAILBOX_ACCOUNT>`, authorized folders, start/end dates and timezone. Select that account through the connector or Gmail account selector. `to:<YOUR_ALIAS>` filters recipients; it does not select a mailbox and can miss forwarded or differently addressed receipts.
- [ ] Inspect query, paging and message-read fields. Translate these [Gmail operators](https://support.google.com/mail/answer/7190?hl=en) to supported fields on other hosts; record lost coverage.
- [ ] Replace `<DATES>` in every example with `after:<START_YYYY/MM/DD> before:<END_EXCLUSIVE_YYYY/MM/DD>`. Replace all remaining placeholders; none is literal Gmail syntax.
- [ ] Set the exclusive end to the day after the last covered date: September 1–30 uses `after:2026/09/01 before:2026/10/01`. For the Gmail API, date literals mean midnight PST; use epoch seconds when exact timezone bounds matter and the host supports them. Check boundary-message timestamps. See [API filtering](https://developers.google.com/workspace/gmail/api/guides/filtering).
- [ ] Use the user's dates; otherwise state a last-13-month window within the authorized scope to catch annual renewals. Honor an explicit all-history request. Search message dates to retrieve evidence, then read the actual charge, invoice and service-period dates separately.

## 2. Run separate candidate searches

Use short date slices for high volume. These are `billing` or `lifecycle` searches, not completed `merchant_discovery`. Run relevant channels; record skips and reasons.

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
- [ ] Prefer sender + short date windows over one giant keyword OR query. If using `-category:promotions` to prioritize a pass, record that exclusion and remove it for merchant closure; it is never a permanent coverage rule.
- [ ] Follow every page token with the same exact query until it ends. A result estimate or the first 100/200 items is not completion. Gmail's [list API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) returns IDs and paging metadata; retrieve message content separately when needed.
- [ ] Split future queries by month/week or merchant when the host truncates results. Cover the whole declared interval, overlap uncertain boundary days and deduplicate by mailbox + message ID. Preserve the original query/result; splitting cannot erase an unfinished page chain already recorded in the audit manifest. Unrecoverable truncation stays provisional.

## 4. Close each merchant's lifecycle search

For every discovered or user-named service, run `merchant_discovery` across the authorized dates using brand, seller, known domains and sender aliases, without billing keywords, category restrictions or promotional exclusions:

```text
<DATES> {from:<MERCHANT_DOMAIN> from:<KNOWN_SENDER_ALIAS> "<BRAND>" "<SELLER_NAME>"}
```

For shared platforms, add a separate search using the observed app/product/account identifier; a Stripe/Apple domain alone does not identify a merchant. Explicitly include aliases: Gmail API searches do not expand them or match whole threads like the Gmail UI does. These are [documented API differences](https://developers.google.com/workspace/gmail/api/guides/filtering).

Add `in:anywhere` only when Spam and Trash are in the authorized scope; set the host's Spam/Trash inclusion option too if required. Otherwise describe the folders excluded. Complete every page and reconcile cancellations, upgrades/downgrades, failed and successful payments, refunds, trial outcomes and reinstatements. Keep date-limited conclusions date-limited.

## 5. Record and finish

- [ ] Preserve exact executed queries, selected account/window/folders, raw result pages, request/next tokens and source IDs under [audit-evidence-contract.md](audit-evidence-contract.md). Use `result_file` for searches and `file` for sources.
- [ ] Give every returned ID a disposition and reason: `reviewed`, `irrelevant`, `unread` or `inaccessible`. An irrelevant result need not have a full download; relevant reviewed messages and attachments need saved content. Record attachments separately.
- [ ] Associate searches and results with real `service_ids`. Shared-channel searches cover multiple candidates: triage each returned ID against that declared set as the contract requires. Use focused follow-ups where possible; never invent a merchant or silently omit noisy results to satisfy the gate.

For a shared query associated with already discovered `service-a` and `service-b`, a clearly unrelated promotion can be recorded as below (illustrative IDs). Here `service_ids` names the scope against which it was excluded, not the promotion's merchant. Relevant messages still need full saved content; ambiguous messages stay unread until resolved.

```json
{"id":"gmail:promo-message-id","service_ids":["service-a","service-b"],"kind":"message","disposition":"irrelevant","note":"Sender, subject and snippet identify a generic webinar invitation; no account, payment or lifecycle event for either service."}
```

- [ ] Stop when the chosen channel passes and every merchant's broad pass are paged and triaged, relevant bodies/attachments are read, and later events are reconciled. Carry unresolved access, identity or coverage gaps into the provisional report. These searches do not prove complete knowledge of the user's accounts.

Primary guidance checked September 16, 2026. Adapt the starting queries to observed senders and languages.
