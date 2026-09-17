# Reports, drafts and follow-up

Default analysis, web interface, report copy, human-readable exports and support drafts to English unless the user explicitly requests another output language. Preserve original source quotations and identifiers, adding translations where useful. A different merchant submission language should be explicitly requested or presented as a clearly labeled optional translation. Keep actual identifiers in private local case material only where the merchant needs them; use local aliases in the overview.

## Artifact set

For an audit, use a private task-owned directory with:

- `audit.json`: the canonical agent-authored observations and decisions under [audit-model.md](audit-model.md), plus imported original evidence and collection records.
- `dashboard.html`: the primary self-contained visual document, with current services, refund questions and other issues. Details contain source timelines, actions and local drafts.
- Generated `dashboard.json`, `facts.json`, `checks.json`, `audit-evidence.json` and `audit-checks.json`: reproducible presentation, arithmetic and evidence/gate views created by `scripts/build_audit.py`. Update the canonical model rather than editing each generated view independently.
- Generated case/outcome views when their data exists; keep independent review packets/results alongside the evidence they bind.

Separate `subscriptions.csv`, narrative `audit.md`, spreadsheet exports and individual draft files are optional requested exports, not routine parallel authoring tasks. The in-page monthly cost sheet and local drafts remain part of the normal report. CSV and webpage inventory must use the same entities and separate invoice/charge/renewal fields. Avoid empty placeholder files.

A single-charge audit keeps the three sections scoped to that charge/service. Follow an explicitly requested alternative output format. Source PDFs and extraction text are working evidence, not default shareable exports. Creating a private dashboard does not authorize hosting its financial/mailbox data.

## Visual document

Use [dashboard-contract.md](dashboard-contract.md) as the single reference for section contents, row classification, billing dates, screening leads and monthly cost calculations.
Use the fixed renderer and the short [webpage preflight](web-design.md). The bundled design guide supplies template-change guidance; ordinary runs use the audit-specific preflight.
Read those references when building or verifying the page, not at the start of evidence collection.

For a requested Excel export, use the host's spreadsheet capability, retain formulas and sources, verify the saved file, and link it as an adjacent local download.
Perform page verification using the checks in `web-design.md`; preserve the source-review gate below.

## Source review before output

Before delivering a full audit, have an independent agent compare the prepared inventory with relevant originals. Generate frozen per-entity packets using `scripts/prepare_review.py` (see `--help`), giving the reviewer the task and sources without expected findings. Each packet binds the row and its actual supporting/conflicting sources; global discovery/cost material covers the chosen queries, exclusions, unsupported named services and monthly inputs. Shared query results are not evidence for every service.

Review every entity for omissions, later lifecycle changes, invoice-versus-payment dates, current-cost inclusion and superseded refund leads/drafts. The reviewer must read the material originals; packet creation, layout checks and an author's summary cannot satisfy source review. Record concrete findings and resolutions under [audit-evidence-contract.md](audit-evidence-contract.md).

Completion requires the prescribed generic invoice/receipt search and applicable channels, complete pagination/triage, material attachment review and reconciliation of later events within scope. A failed/unsupported required discovery step stays provisional. Broader searches and older history are separate requested follow-ups; annual plans without a notice in six months may be absent.

Review one frozen prepared version. After a correction, re-review affected rows/sources and check report-wide costs/coverage. Unchanged entity findings may be carried forward only after verifying their row and relevant evidence remain unchanged; refresh the final report/evidence binding after that review. No automatic hash refresh may turn old approval into approval of changed material. If the reviewer fails or is unavailable, record the limit and deliver a provisional report rather than retrying indefinitely.

For an explicitly requested first-output evaluation, preserve the author's first complete proposal before feedback, use an author without prior answers, and record corrections separately. Timing traces, screenshot matrices and first-proposal archives belong to that evaluation, not every normal audit. Synthetic/program checks and saved-packet reviews do not establish live mailbox discovery quality or runtime. For runtime comparisons, record the exact skill revision, host/model settings, source window, live versus replay mode and environment failures. Measure first HTML and final reviewed delivery separately; keep the comparison scope consistent and report known omissions alongside elapsed time.

Run the executable gate after resolving correctable review findings, with absolute paths resolved from the skill and private working directory:

```text
python scripts/check_audit.py --report dashboard.json --evidence audit-evidence.json --output audit-checks.json
python scripts/render_dashboard.py --input dashboard.json --evidence audit-evidence.json --output dashboard.html --require-checked
```

Inspect the gate findings before the render step. The renderer recomputes the gate rather than trusting a supplied pass label; `--require-checked` is required when completing a new full audit. The webpage must visibly show **source-scope coverage passed** or **provisional**, with unresolved source/review gaps. Missing manifests, unread material billing attachments, truncated searches or incomplete required review prevent a finalized coverage claim. If a gap cannot be resolved within the authorized scope, omit `--require-checked` only to provide an explicitly provisional report; do not call the audit complete. Use `--force` when intentionally replacing existing outputs if the helper requires it.

The gate checks documented retrieval, review and report consistency. It does not read every source itself or certify that all facts are true. A genuine unknown payment date can coexist with passed scoped coverage when the relevant evidence was completely reviewed and the uncertainty is accurately stated. Rerun the gate and renderer whenever evidence, lifecycle status or financial conclusions change.

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
