# Tabs

Segmented tabs for switching views within one page (Overview / Trace / Output).

## Props
- `items`: `[{ value, label, icon?, count? }]`.
- `value` + `onChange` (controlled) or `defaultValue` (uncontrolled).
- `label` — aria-label for the tablist.

## Do / don't
- 2–5 tabs. Labels are one or two words, sentence case.
- The page owns the panels; Tabs only reports the selection.
