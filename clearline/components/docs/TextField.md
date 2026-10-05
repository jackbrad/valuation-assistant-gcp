# TextField

Single-line text input with a label above, optional leading icon, and help or error text below.

## Props
- `label` — always provide one; it sits above the field in `label` style.
- `help` — muted helper line. `error` — replaces help, turns the border `danger`, adds an error glyph.
- `icon` — leading Material Symbols name (search, mail…).
- Any `<input>` attribute passes through (`value`, `onChange`, `placeholder`, `type`).

## Do / don't
- Error copy says what to do next ("Paste a new one"), not just what failed.
- Don't use placeholder text as the label.
