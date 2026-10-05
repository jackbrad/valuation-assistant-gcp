# PromptBox

The AI input: a multi-line prompt, an optional tool row, model/meta text and a Send button (Cmd/Ctrl+Enter submits).

## Props
- `onSubmit(text)` — called on Send or Cmd/Ctrl+Enter.
- `placeholder`, `defaultValue`, `rows` (default 2), `label` (aria-label, default "Prompt").
- `meta` — mono text in the bar: model name, tool count, token budget.
- `tools` — icon-only ghost Buttons for attach/settings (each with `aria-label`).
- `busy` — disables Send and shows "Running…".

## Do / don't
- Do use it as the hero of an AI demo, centred, max 720px wide.
- Don't stack two PromptBoxes on one screen.
