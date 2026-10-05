# Table

Data table with sunken header, hairline rows, right-aligned numbers and mono IDs.

## Props
- `columns`: `[{ key, label, align?: 'right', mono?: true, render?(row) }]`.
- `rows`: plain objects; `id` used as the key when present.
- `caption` — screen-reader caption (visually hidden).

## Do / don't
- Right-align numbers, set IDs/model names `mono`.
- Status columns use Badge, never coloured text alone.
