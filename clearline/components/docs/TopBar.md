# TopBar

Product header for every demo screen: mark, product name, a context crumb and actions.

## Props
- `product` (string, required) — the product name, set in `title` weight.
- `context` — a breadcrumb or workspace name, shown muted after a hairline.
- `markIcon` — a Material Symbols name for the square mark (default `bolt`). There is no logo; the mark is a `primary` tile with an icon.
- `actions` — React nodes, right-aligned. Two at most: one `ghost` + one `primary` Button.

## Do / don't
- Do put exactly one TopBar at the top of each screen, full width, on `surface-raised`.
- Don't add navigation tabs inside it; put Tabs under it in the page.
