# Audit webpage design integration

## Design guidance for audit webpages

For a routine focused review or requested full audit using the existing renderer, use this integration as a short preflight. Read the **complete bundled [design-taste-frontend skill](design-taste-frontend/SKILL.md)** when changing the template, layout or visual style. The bundled file is a full, unmodified portable copy, not a dependency on another user's skill directory. Resolve it relative to this reference. Explanatory answers that do not produce a webpage do not require the design pass.

## Apply the design brief honestly

The bundled design skill explicitly excludes dashboards and data tables from its primary landing-page scope. This report is a private financial document; its inventory is limited by the declared focused or full-audit scope. Use the user request, audit instructions and [dashboard contract](dashboard-contract.md) to determine scope; apply the design skill's context-relevant guidance to typography, color, spacing, layout, interaction, accessibility and preflight. Its marketing-page prescriptions do not replace the report's data or delivery requirements.

Use a short design read before page work: a calm, precise financial document for reviewing services and deciding what to investigate. Set modest visual variance, minimal motion and enough density to scan a complete inventory. Native CSS and the bundled renderer are the intended foundation for this offline document. Do not introduce React, remote packages, a marketing framework or a server solely to satisfy a landing-page default.

## Preserve the audit

- Keep the three sections in order: **Current services**, **Refund questions**, **Other issues**. Retain explicit empty states.
- Show the renderer's focused, provisional or checked status above the inventory. A focused page states its selected evidence boundary; a provisional full audit lists unresolved checks. Styling must not imply that source coverage or independent review has passed.
- Keep every discovered or user-named service in the data and accessible in the page, including uncertain, normal and resolved entries. Filters may narrow a view, but show the result count and a clear way to restore all items. Do not replace a complete inventory with selected highlights, a carousel or decorative tiles.
- Present status/dates and monthly costs as two views of one inventory. Use accessible tabs and shared filters; explain that listed entries include uncertain and historical services. Keep a full-inventory baseline explicitly labeled when filters hide rows.
- Highlight proactive review leads with words and a semantic color in both views. Show their reason and next check in a separate queue within Refund questions, before specific refund cases. Count leads separately from claims and never style a possible-overlap or usage-unknown signal as confirmed refund eligibility.
- Preserve dated evidence, unknowns, amount semantics, eligibility state, draft conditions and source links. Visual emphasis must not turn an uncertain charge into an approved refund or an incomplete fixed-cost subtotal into total spending.
- Use actual service rows and evidence details. Do not create decorative generated imagery, fictional screenshots, social proof, testimonials or conversion calls to action. Never send private bills or mailbox data to image-generation services for page decoration.
- Keep English as the default for interface labels, report copy and human-readable exports unless another language is explicitly requested. Preserve original source quotations with translation as needed. Do not rewrite evidence to fit a stylistic punctuation or brevity rule.

## Context-relevant design choices

Use a coherent sans-serif type system with clear heading levels, comfortable text sizes and tabular numbers for money. Distinguish state labels with words as well as color. Keep explanatory text close to the amount or claim it qualifies; move deeper evidence into accessible details rather than deleting it.

Use one consistent accent and neutral scale, with semantic status colors only where they convey a real difference. Define light and dark tokens at the document level, respect system preference and preserve equivalent hierarchy and contrast in both themes. Maintain a consistent radius and spacing scale. Avoid a large marketing hero, ornamental gradients, repeated decoration labels and unnecessary card containers.

Design the inventory for scanning on desktop and reading on narrow screens. A responsive table or structured rows are appropriate even though the bundled landing-page guide discourages long tables in marketing pages. Give filters persistent labels, and make details, dismiss controls, source links and copy actions keyboard accessible. Show useful empty states when filters return no results.

Motion should communicate a state change or feedback and respect reduced-motion preferences. Do not hide financial content behind scroll reveals or introduce scroll hijacking, parallax, marquees or automatic decorative animation.

## Offline and privacy constraints

The output remains one self-contained HTML document with supporting JSON; a requested full audit may also have CSV exports. Use embedded CSS/JavaScript, system fonts or appropriately licensed embedded font data with a fallback. Do not fetch fonts, images, trackers, packages or other assets when the document loads. Explicit source/support links may navigate only when the user follows them. Keep raw email HTML, access tokens and unnecessary identifiers out of the presentation.

## Preflight

For a routine focused review or full audit with the existing renderer, apply the checks below. When changing the template, layout or visual style, read the bundled preflight in full and apply its relevant checks to this financial-document brief. Mark marketing-only checks as inapplicable with a brief reason; do not add imagery, truncate evidence or convert the page into a landing page merely to tick them.

Before delivery, verify:

1. All three sections and the complete service inventory are present; issue groups and monthly components agree with the JSON.
2. English copy is complete by default, uses plain language and labels uncertainty. Original-language source quotations remain traceable.
3. Light and dark themes have readable text, labels, inputs, buttons and focus indicators; state does not rely on color alone.
4. Mobile layout preserves amounts, service names, evidence access and action controls without clipped content.
5. Filters, detail views, close controls and copy feedback work through the host's permitted checks; hidden filtered rows can be restored.
6. Motion respects reduced-motion settings, and the document loads without remote-resource requests.
7. Every visible amount, date and outcome remains sourced or explicitly synthetic; neither styling nor copy implies that a draft was sent.

Use the host's allowed preview and verification tools. Report checks actually performed and any remaining verification gap; do not claim a visual or accessibility test that was not run.
