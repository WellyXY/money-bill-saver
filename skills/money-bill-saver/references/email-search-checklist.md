# Focused email search

Use this checklist for the default six-month mailbox review. Search one selected account at a time. Its purpose is to find the latest material costs and concrete billing questions quickly; the page must say which searches and folders it covers.

## Scope

Record account, timezone, inclusive first/last dates and excluded folders. In Gmail, use `after:<START> before:<END_EXCLUSIVE>` on every query. Gmail date literals use a fixed PST boundary; use epoch seconds when the exact selected timezone boundary matters. Keep the executed query and page tokens. The search date is not an invoice, payment or renewal date.

## 1. One billing discovery query

Search high-signal billing, trial and subscription **subjects**, plus Stripe sender mail, across categories. Include archived mail if authorized:

```text
<DATES> {subject:invoice subject:receipt subject:"billing statement" subject:"free trial" subject:"free trail" subject:trial subject:subscription from:stripe.com subject:發票 subject:收據 subject:帳單 subject:月結單 subject:應付憑據}
```

Page the same query until its next-page token ends. Deduplicate by account + message ID. Save the result IDs, sender, subject, date and snippet; fetch no bodies yet. Use `from:stripe.com` instead of a bare `Stripe` word, and `subject:subscription` instead of a bare `subscription` word, to avoid broad newsletter matches. These are candidate clues, not proof of a paid subscription or settled charge. If the provider lacks sender or subject search, use its closest billing query and state the substitution.

Triage each hit into: **current cost**, **specific payment/refund/renewal question**, **possibly relevant**, or **unrelated**. Read full bodies for the first two groups and ambiguous hits that may change them. For each merchant, read its latest material bill first. Older bills are needed only for a price change, conflict or particular refund period. Batch clear promotions and routine one-time receipts into a count and reason; they do not need individual body reads or report rows. Keep user-named services visible even if no message matches.

## 2. Check later outcomes for issue-bearing merchants

For a disputed charge, failed payment, refund, cancellation, plan change or benefit claim, use the known merchant account and sender aliases to find **all later support replies in this six-month window**. Start with the related thread when its full message list is available. Otherwise search the confirmed sender(s) without mandatory lifecycle keywords, triage those result headers, and read the relevant conversations. If the sender returns too much mail, narrow by the charge, invoice ID, account or support-thread subject while retaining later messages.

Words such as `waived`, `waiver`, `credit`, `adjustment`, `dispute`, `resolved`, `refund`, `cancelled`, `免除` and `抵免` help prioritize hits; they are not the only admission rule. A notice saying payment failed is not a current debt when later support may have waived it. Match a resolution to the same account and charge before reporting it.

For a named merchant that was not found, run one focused sender/product/account search within the same date window. A no-result search supports only “not found in these searches,” not “no subscription exists.”

## 3. Open another channel only for a concrete gap

- A named processor-billed merchant still lacks a receipt after the initial Stripe sender search: filter the saved Stripe results by seller/product/account first; search a different known processor or a targeted merchant alias only if needed. Do not repeat the same Stripe query.
- An App Store purchase is named or observed: search its known Apple receipt phrases and account. Do not treat Apple as the service vendor.
- A specific card charge is questioned: search a known card-alert sender and merchant/amount; an alert is not settlement evidence.
- A trial or renewal question lacks a bill: search the named service's trial or renewal notice. Verify the later plan state.
- One-time purchases are in scope at the user's request: use `category:purchases` or a targeted merchant, then triage headers first.

Do not automatically run every channel, an unrestricted brand sweep, or an older-history search. Record skipped channels as coverage limits. When a query produces only unrelated results, stop expanding and record why. Preserve unresolved material sources as explicit unknowns in the page.

## Timed handoff

The discovery stage saves a compact candidate index and exact query/page log. The evidence stage receives IDs and reasons, reads the selected messages, and can run the issue-specific outcome checks. Stage handoffs carry source IDs and counts; they do not require a second reading of already saved messages. For an explicitly requested exhaustive `audit-1` verification, use the separate [evidence contract](audit-evidence-contract.md) and complete its per-result dispositions and coverage gate.
