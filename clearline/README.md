# Clearline design system

A calm, precise UI kit for product demos and prototypes. It has light and dark themes, the Figtree and JetBrains Mono fonts, Material Symbols Rounded icons and 12 React components.

**Read `DESIGN.md` first.** It's the brand book: principles, copy rules, color usage, type, spacing, focus states and screen patterns.

## What's in here

```
clearline/
├── README.md                  ← you are here
├── DESIGN.md                  ← brand book / usage rules (source of truth)
├── tokens/
│   ├── tokens.json            ← all tokens as data (colors per theme, type, spacing, radius, shadow)
│   ├── tokens.css             ← CSS custom properties + type classes (.display, .title, .body, .code …) + font imports
│   └── tailwind.preset.js     ← optional Tailwind preset mapped to the CSS variables
├── components/
│   ├── clearline.css          ← component styles (.cl-* classes); needs tokens.css loaded first
│   ├── clearline.umd.js       ← no-build version: sets window.Clearline (needs React 18 globals)
│   ├── clearline.d.ts         ← prop types for every component
│   └── docs/<Component>.md    ← per-component props, do's and don'ts
├── react/
│   ├── index.js               ← ES module version: import { Button } from './clearline/react'
│   └── index.d.ts
└── examples/
    └── demo.html              ← a full example screen; open in a browser
```

## Use it in a React app (Vite, Next.js and similar)

1. Copy the `clearline/` folder into the project, e.g. `src/clearline/`.
2. Import the styles once at the app root, in this order:
   ```js
   import './clearline/tokens/tokens.css';
   import './clearline/components/clearline.css';
   ```
3. Use the components:
   ```jsx
   import { TopBar, Button, PromptBox, Metric, Table, Badge } from './clearline/react';
   ```
4. Theme: light is the default. Set `document.documentElement.dataset.theme = 'dark'` for dark. Without a `data-theme` attribute, the page follows the operating system's setting.

## Use it without a build step

Load the files in this order: `tokens.css`, `clearline.css`, React 18 UMD, ReactDOM 18 UMD, then `clearline.umd.js`. The components are then on `window.Clearline`. See `examples/demo.html`.

## Use the tokens only (any framework, or Tailwind)

- Plain CSS: load `tokens/tokens.css` and use `var(--primary)`, `var(--space-5)`, `var(--radius-lg)`, plus classes like `.display` and `.body`.
- Tailwind: add `presets: [require('./clearline/tokens/tailwind.preset.js')]`. You get classes like `bg-surface-raised text-ink border-line rounded-lg shadow-1 text-title p-5`. Spacing keys 1–8 are Clearline's steps (4→64px).

## Components

TopBar · Button · TextField · PromptBox · Tabs · Switch · Card · Metric · Table · Badge · Banner · Icon (see `components/docs/`).

## Rules that matter most

- Use only the tokens. Don't hard-code hex values, pixel sizes outside the spacing scale, or other fonts.
- `primary` (Lagoon teal) is the only brand hue. `accent` (Marigold) appears at most once per screen.
- Status always pairs color with a word and an icon.
- Sentence case everywhere, buttons start with a verb, no emoji, and real data instead of lorem ipsum.
