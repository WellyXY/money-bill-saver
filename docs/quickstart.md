# Money Bill Saver quickstart

Review services, costs and billing questions. **About a 50-second read**; audit completion time varies with evidence and access.

## 1. Install

With **Node.js and Git** installed, paste this into your terminal:

```sh
npx --yes skills add WellyXY/money-bill-saver --skill money-bill-saver --agent codex --global --yes
```

Prefer Codex chat? Use the [skill-installer alternative](../README.md#try-it-in-codex).

## 2. Try fictional bills

Open a new Codex task and paste:

```text
Use $money-bill-saver to render and explain the bundled synthetic example report. Do not access my mailbox or personal files.
```

![Synthetic preliminary report with summary metrics and the current services inventory](assets/report-preview.png)

- **Current services:** see plans, billing dates and the Monthly cost sheet. Uncertain and historical services stay visible.
- **Refund questions:** follow evidence and next checks. A question does not establish refund entitlement.
- **Other issues:** renewals, unknown prices, missing benefits and evidence gaps.

[Explore the interactive tour](https://wellyxy.github.io/money-bill-saver/) · [Open the synthetic report](https://wellyxy.github.io/money-bill-saver/example-report.html)

## 3. Choose your real review

Replace the placeholders and omit any source you do not want reviewed:

```text
Use $money-bill-saver to review [local files or folder] and billing mail in [mailbox/account] from [start date] through [end date]. Read only these sources. Deliver a private English webpage with services, monthly costs, refund questions, other issues and evidence gaps. Prepare support drafts for my review.
```

There is no bundled mail connector. Mailbox review needs an authorized connection; local bills and exports work without one.
