# Metric

A single KPI: label, big tabular number, optional unit and trend delta.

## Props
- `label`, `value` (string, pre-formatted), `unit`.
- `trend`: `up` · `down` · `neutral`; `delta` text beside the arrow.
- `good` — whether the trend is good (default: up is good). Colours `success`/`danger`, always with an arrow and words.

## Do / don't
- Real numbers from the demo only; three or four tiles max per row.
- Don't use for anything that isn't a number.
