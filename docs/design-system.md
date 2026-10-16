# Design system — editorial enterprise

Read this before writing any CSS, Streamlit styling or `.streamlit/config.toml` theme
values. Native widgets are themed through `config.toml`; the few custom HTML blocks
live in `src/process_agent/ui/components/theme.py`.

## Design language
Calm, editorial, high-contrast enterprise UI. Generous whitespace, hairline dividers,
a single confident accent (grape) against warm stone neutrals. Display type is light
and tightly tracked; small labels are uppercase and widely tracked. Restraint over
decoration — no gratuitous animation on a data app.

Signature elements:
- **Eyebrow labels** — `■ SMALL UPPERCASE` with a 7px grape square (`eyebrow()`).
- **Bracketed stats** — headline numbers framed by corner brackets (`stat_strip()`).
- **Numbered sections** — `01 / 02 / 03` columns split by hairlines (`numbered_steps()`).
- **Flow strip** — numbered pipeline with a grape → dusk → amethyst rail (`flow_strip()`).
- **Dark hero** — night background, faint grid, two-tone headline (muted → bright),
  bracketed live-stat chips (`hero()`).

## Fonts
| Role | Family | Notes |
|---|---|---|
| Body | Inter 400–600 | `font` in config.toml |
| Display / headings / metric values | Inter Tight 300–500 | weight 400, letter-spacing −0.03 to −0.04em |
| Code | JetBrains Mono | `codeTextColor` amethyst |

## Color tokens
```css
:root {
  --white: #ffffff;
  --night: #161714;        /* primary text / dark surfaces */
  --grape: #9677ff;        /* accent — primary CTA, links, highlights */
  --amethyst: #4e287a;     /* accent-hover / code text */
  --ocean: #e5f8ff;
  --sky: #97c8ff;
  --dusk: #6474cd;         /* secondary accent, gradient mid-point */
  --raspberry: #985fca;
  --gray: #81837a;         /* muted text */

  --midnight-25: #4a4b44;  /* body copy on light surfaces */
  --stone-25: #f7fbf5;     /* sidebar, dataframe header */
  --stone-50: #e7ebe5;     /* hairlines, dividers */
  --stone-75: #d8dad1;
  --stone-100: #c3c6bb;
  --sage: #f4f7f2;         /* secondary background, widget fills */
}
```

## Status palette (charts, badges, process map)
Validated for colour-vision deficiency (lightness band, chroma floor, CVD ΔE ≥ 8,
contrast ≥ 3:1). Always paired with an icon and label — never colour alone.

| Status | Mark | Tint (node fill) | Badge |
|---|---|---|---|
| Automatable | `#2d9bc4` | `#e1f2f9` | blue |
| Human review | `#8b6cf5` | `#efebfe` | violet |
| Bottleneck | `#d6645a` | `#fbe6e3` | red |

Gate decisions use green (APPROVED), red (DENIED) and orange (ESCALATED) badges.

## Shape, spacing, motion
- Radius: **6px** for cards, inputs and buttons (`baseRadius`, `buttonRadius`).
- Borders: 1px hairlines in `#e1e5de` / `--stone-50`. No heavy black rules.
- Spacing: multiples of 4px; use `st.space()` rather than dividers.
- Motion: none beyond Streamlit defaults.

## Rules
- Prefer native Streamlit elements; use custom HTML only for the signature elements above.
- Material Symbols (`:material/icon:`) over emoji.
- Sentence case for titles and labels.
- One y-axis per chart; categorical colours in fixed order; legends for ≥ 2 series.
