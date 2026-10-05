# Card

The container for one idea: eyebrow, title, body, optional actions and footer.

## Props
- `eyebrow` — small uppercase kicker (step number, category).
- `title` — in `title` style.
- `children` — a string renders as muted body copy; nodes render as given.
- `actions` — top-right node (a Badge or small Button).
- `footer` — actions row under a hairline.
- `flat` — drops the shadow (cards inside cards, dense grids).

## Do / don't
- Cards sit on `surface` with `space-5` gaps. Don't nest a shadowed card in a card.
- No coloured left borders; status goes in a Badge.
