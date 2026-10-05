# Button

The action control: one primary per view, secondary for alternatives, ghost for low-emphasis, danger for destructive.

## Props
- `variant`: `primary` (default) · `secondary` · `ghost` · `danger`.
- `size`: `sm` 32px · `md` 40px (default) · `lg` 48px (title screens only).
- `icon` / `iconEnd`: a Material Symbols name.
- `children`: the label. Sentence case, a verb first ("Run agent", not "Agent Run" or "OK").
- Any `<button>` attribute passes through (`onClick`, `disabled`, `type`).

## Do / don't
- One `primary` per screen region. Pair it with `secondary` or `ghost`, never two primaries.
- Icon-only buttons need `aria-label`.
