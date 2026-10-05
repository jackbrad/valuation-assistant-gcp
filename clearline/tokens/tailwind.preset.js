/* Clearline Tailwind preset. Import tokens.css once globally, then:
   module.exports = { presets: [require('./clearline/tokens/tailwind.preset.js')], ... }
   Classes: bg-surface, text-ink, text-ink-muted, bg-primary, text-on-primary, border-line, rounded-lg, shadow-1, p-5 (=space-5 24px), text-title, font-mono ...
   NOTE: numeric spacing keys 1-8 map to Clearline steps (4,8,12,16,24,32,48,64px), overriding Tailwind defaults. */
module.exports = {
  "theme": {
    "extend": {
      "colors": {
        "surface": "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        "surface-sunken": "var(--surface-sunken)",
        "line": "var(--line)",
        "line-control": "var(--line-control)",
        "ink": "var(--ink)",
        "ink-muted": "var(--ink-muted)",
        "primary": "var(--primary)",
        "primary-hover": "var(--primary-hover)",
        "primary-soft": "var(--primary-soft)",
        "on-primary": "var(--on-primary)",
        "accent": "var(--accent)",
        "on-accent": "var(--on-accent)",
        "accent-text": "var(--accent-text)",
        "accent-soft": "var(--accent-soft)",
        "success": "var(--success)",
        "success-soft": "var(--success-soft)",
        "danger": "var(--danger)",
        "danger-soft": "var(--danger-soft)",
        "focus-ring": "var(--focus-ring)",
        "link": "var(--link)"
      },
      "spacing": {
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "5": "24px",
        "6": "32px",
        "7": "48px",
        "8": "64px"
      },
      "borderRadius": {
        "sm": "6px",
        "md": "10px",
        "lg": "16px",
        "full": "999px"
      },
      "boxShadow": {
        "1": "var(--shadow-1)",
        "2": "var(--shadow-2)"
      },
      "fontFamily": {
        "sans": [
          "var(--font-sans)"
        ],
        "mono": [
          "var(--font-mono)"
        ]
      },
      "fontSize": {
        "display-lg": [
          "56px",
          {
            "lineHeight": "60px",
            "fontWeight": "650",
            "letterSpacing": "-0.02em"
          }
        ],
        "display": [
          "40px",
          {
            "lineHeight": "48px",
            "fontWeight": "650",
            "letterSpacing": "-0.015em"
          }
        ],
        "headline": [
          "28px",
          {
            "lineHeight": "36px",
            "fontWeight": "600",
            "letterSpacing": "-0.01em"
          }
        ],
        "title": [
          "20px",
          {
            "lineHeight": "28px",
            "fontWeight": "600"
          }
        ],
        "body-lg": [
          "17px",
          {
            "lineHeight": "26px",
            "fontWeight": "400"
          }
        ],
        "body": [
          "15px",
          {
            "lineHeight": "22px",
            "fontWeight": "400"
          }
        ],
        "label": [
          "13px",
          {
            "lineHeight": "18px",
            "fontWeight": "600",
            "letterSpacing": "0.01em"
          }
        ],
        "caption": [
          "12px",
          {
            "lineHeight": "16px",
            "fontWeight": "500"
          }
        ],
        "metric": [
          "32px",
          {
            "lineHeight": "40px",
            "fontWeight": "500",
            "letterSpacing": "-0.02em"
          }
        ],
        "code": [
          "13px",
          {
            "lineHeight": "20px",
            "fontWeight": "400"
          }
        ]
      }
    }
  }
};
