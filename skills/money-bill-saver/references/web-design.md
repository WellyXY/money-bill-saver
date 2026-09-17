# Audit webpage preflight

## Reading scope

The report uses the fixed `assets/dashboard.html` template through `scripts/render_dashboard.py`.
For an ordinary audit, read this short integration and **only Section 14: FINAL PRE-FLIGHT CHECK** in the bundled [design-taste-frontend guide](design-taste-frontend/SKILL.md#14-final-pre-flight-check).
The full upstream guide stays bundled, with its license, for an explicitly requested redesign; it is not a normal audit prerequisite.
Do not follow its cross-references into unrelated sections merely to complete the preflight.

From the installed skill directory, extract that section by heading instead of reading the whole file:

```sh
awk '/^## 14\. FINAL PRE-FLIGHT CHECK/{show=1} /^# APPENDICES/{show=0} show' references/design-taste-frontend/SKILL.md
```

Apply relevant checks for readable copy, typography, theme consistency, contrast, controls, mobile layout and reduced motion.
The audit contract governs financial content. Marketing hero, imagery, logo-wall, CTA conversion, decorative animation, table-length and punctuation prescriptions do not apply to this fixed financial report.
Keep source quotations intact and every service accessible. Do not add packages or redesign the renderer during an ordinary audit.

## Report preflight

1. **Content:** the three required sections, full service inventory, issue groups, dates and monthly components match `dashboard.json`; unknowns and the coverage boundary remain visible.
2. **Status:** the renderer's completion/provisional label is visible. Screening leads are distinct from refund cases; neither styling nor copy implies guaranteed eligibility or a sent draft.
3. **Language:** English by default or the requested language; original evidence stays traceable and is not rewritten to satisfy style rules.
4. **Readability:** check light/dark text and control contrast, semantic labels beyond color, and keyboard focus. Narrow layouts retain amounts, names and evidence access without clipping.
5. **Interaction:** verify tabs, shared filters, restoring all rows, detail/close controls, evidence links and copy feedback. Filters preserve the full-inventory baseline.
6. **Offline/privacy:** no automatic remote asset requests, raw email HTML, tracking pixels or access tokens in the page. Explicit support/source links open only on user action.
7. **Motion:** retain usable content with reduced motion; no decorative animation is required.

Use the host's permitted preview tools. Report only checks actually performed and any remaining verification gap.
