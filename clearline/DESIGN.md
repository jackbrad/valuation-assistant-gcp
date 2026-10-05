Clearline is a calm, precise system for building product demos and prototypes that have to hold up in front of a room: clean Material-informed structure on an 8px rhythm, one confident brand hue (Lagoon teal), one highlight (Marigold), and nothing decorative that doesn't carry meaning.

## Principles

- **One idea per screen.** Each demo screen answers one question. If it needs two, it's two screens.
- **The data is the hero.** Real numbers, real IDs, real copy. No lorem ipsum, no filler stats, no stock illustrations.
- **Quiet chrome, loud content.** Surfaces separate by tone and a hairline first, shadow second. Colour is spent on state and the single primary action.
- **Show the machine.** For AI features, expose what the agent did: tool calls, latency, cost, confidence. Trust comes from visible reasoning.

## Content fundamentals

- Sentence case everywhere: buttons, titles, tabs ("Run agent", not "Run Agent").
- Buttons start with a verb. Banners say what happened, then what to do ("Retried 3 times. Check the trace for the tool error.").
- Address the user as "you"; the product speaks as "we" sparingly. No exclamation marks, no emoji.
- Numbers: use units and real precision (`38.4 s`, `$0.021`, `97.2%`). Use an en dash or "—" for empty cells, never "N/A".
- IDs, model names, prompts and JSON are set in `code` (mono).

## Colour

- Ground is `surface`; cards, panels and inputs are `surface-raised`; wells and table headers are `surface-sunken`.
- Text is `ink`; secondary text is `ink-muted`. Both hold 4.5:1+ on all three surfaces in light and dark.
- `primary` (Lagoon) is the only brand hue in the UI: the primary button, active tab, links, selection. Text on a `primary` fill is `on-primary`, never literal white.
- `accent` (Marigold) is a highlight fill, used once per screen at most (the `new` badge, a "look here" marker). As text, use `accent-text`.
- Status: `success`, `accent-text` (warning) and `danger`, each on its `-soft` ground. Success and danger differ by hue more than lightness, so every status always carries a word and a glyph (Badge and Banner add one automatically).
- Hairlines are `line`. Control borders (inputs, switches, secondary buttons) are `line-control`, which holds 3:1 on every surface.

## Type

- One family: **Figtree** (Google Fonts) for everything, **JetBrains Mono** for code and IDs. Load both from Google Fonts; `components/bundle.css` already imports them.
- Scale: `display-lg` 56 for one hero line, `display` 40 for page titles, `headline` 28 for sections, `title` 20 for cards, `body-lg` 17 for narrative, `body` 15 default, `label` 13 for controls and headers, `caption` 12 for metadata, `metric` 32 for KPI numbers (tabular figures), `code` 13 mono.
- Tighten tracking only on display sizes (already in the tokens). Never set body copy in bold to create hierarchy; step the scale instead.

## Space, shape, depth

- 4px base: `space-1` 4 through `space-8` 64. Card padding `space-5`; gap between cards `space-5`; between page sections `space-6`/`space-7`; desktop page margin `space-7`.
- Radii: `radius-sm` 6 for badges, `radius-md` 10 for controls, `radius-lg` 16 for cards and panels, `radius-full` for switches and pills.
- `shadow-1` on resting cards, `shadow-2` on menus and popovers only. No coloured shadows, no gradients.
- Layout: a 12-column grid, max content width 1200px, centred. Title screens can go to `space-8` margins.

## Focus and states

- Keyboard focus is a solid 2px `focus-ring` outline offset 2px, on every interactive element. It holds 6:1 on every surface in both themes.
- Hover darkens fills (`primary-hover`) or tints with `surface-sunken`; disabled is 45% opacity with a not-allowed cursor.
- Motion: 150ms ease on colour and position changes only. Nothing bounces.

## Iconography

- **Material Symbols Rounded** (Google Fonts), outline style, weight 400, at 20px in controls and 24px standalone. Use the `Icon` component or the `.cl-icon` class with the symbol name as text.
- Icons inherit `color`: `ink-muted` by default, `primary` when active, the status colour inside status components.
- There is no logo. The product mark is a `primary` square (`radius-md`-ish 8px) with a filled Material Symbol, as in `TopBar`. Set the product name in Figtree 650.

## Using the components

- Load React 18, then `components/bundle.css` and `components/bundle.js`; everything is on `window.Clearline` (`Button`, `TextField`, `PromptBox`, `Tabs`, `Switch`, `Card`, `Metric`, `Table`, `Badge`, `Banner`, `TopBar`, `Icon`).
- Set `data-theme="light"` or `"dark"` on `<html>` to switch themes.
- A typical demo screen: `TopBar`, then a `display` title and one `body-lg` sentence, then either a centred `PromptBox` (AI demos) or a row of `Metric` tiles over a `Table` or a grid of `Card`s.
