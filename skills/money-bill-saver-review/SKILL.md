---
name: money-bill-saver-review
description: Independently verify a Money Bill Saver report against original billing evidence when the user explicitly asks for detailed review.
---

# Money Bill Saver Review

Run this only for an explicit request to independently verify an existing Money Bill Saver result. Work in a separate agent with the report and its saved originals. Record the report revision and what sources are actually available before checking claims.

## Focus the review

1. Compare consequential claims with originals: monthly costs, last successful charges, next renewals, refund or payment recommendations, drafts, and conflicting later service events.
2. Check whether a related support thread or bounded sender/account search has a later resolution. A search keyword list cannot establish that no resolution exists.
3. Read original attachment pages only when a material amount, date, identity or term remains unclear after text extraction.
4. Record each correction with its source and distinguish a missing source from a factual contradiction. Do not turn a missing use record into proof of non-use or refund eligibility.
5. Return a short findings list and a revised report only when authorized to edit it. State the scope actually reviewed; do not claim complete mailbox coverage.

For an explicitly requested exhaustive audit of all entities and sources, use the main skill's [evidence contract](../money-bill-saver/references/audit-evidence-contract.md) and [optional review procedure](../money-bill-saver/references/deliverables.md#optional-independent-verification). The `prepare_review.py` and `check_audit.py` helpers apply to `audit-1` evidence bundles. A focused `quick-1` webpage has not passed that exhaustive gate; reconstruct an `audit-1` bundle only if the user requests that level of verification.

Keep saved financial records private. Sending merchant messages or changing account settings requires separate authorization.
