# Audit webpage preflight

## Reading scope

Ordinary audits use the fixed `assets/dashboard.html` through `scripts/render_dashboard.py`.
This short report preflight is the routine integration of bundled **design-taste-frontend**: preserve readable type, contrast, semantic status labels, usable controls and the existing responsive layout.
The full [design guide](design-taste-frontend/SKILL.md) and its license remain bundled for template changes or an explicitly requested redesign.

For a template change, start with Section 14 of that guide, then read only the design sections relevant to the change:

```sh
awk '/^## 14\. FINAL PRE-FLIGHT CHECK/{show=1} /^# APPENDICES/{show=0} show' references/design-taste-frontend/SKILL.md
```

Financial content follows the audit contract. Marketing hero, imagery, logo-wall, conversion, decorative animation and table-length rules do not shorten the inventory or alter evidence.

## Ordinary report check

1. **Data:** inspect generated checker findings. Both inventory views share all service rows; dates, costs, issue groups and unknowns use the same canonical data. A document's arithmetic is distinct from its payment/status evidence.
2. **Display:** open the generated page using permitted host tools and confirm it loads, the three sections appear, long names/amounts remain readable, and the source-scope/provisional label and material gaps are visible. Check one populated detail if available. If preview is unavailable, state that gap; file generation alone does not prove browser display.
3. **Actions and privacy:** confirm drafts are local and unresolved eligibility is visible. Use the unchanged self-contained template; no automatic remote assets, raw email HTML, tracking pixels or access tokens. Source/support links require user action.

A new template defect or content-specific display problem warrants a focused follow-up. Ordinary runs do not need repeated theme/device screenshot matrices, full filter/clipboard regressions or visual polishing.
Report only checks performed. Keep screenshots and benchmark bookkeeping optional unless requested.

## Template-change verification

When renderer, template, styles, interactions or design change, check:

- All three sections and empty states; full inventory accessible in both views.
- Shared search/filter, restoring rows, detail/close controls, evidence links and copy feedback.
- Full-inventory monthly baseline unchanged by display filtering.
- Light/dark contrast, keyboard focus and labels beyond color.
- Narrow viewport with amounts/names accessible; wide cost table scrolls internally without page overflow.
- Reduced motion, no automatic remote requests, and no page errors.

Use the host's permitted preview tools and synthetic data. Keep source review separate from browser verification.
