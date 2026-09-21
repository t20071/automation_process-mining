# SKILL: Web Design — Minimal Editorial Style

Use this style for any UI/web page in this project (Streamlit app, static pages,
or component styling). Read this file before writing any CSS or Streamlit
`st.markdown`/custom-component styling.

## Design language
Minimal, editorial, high-contrast. Generous whitespace, soft rounded corners,
a single confident accent color against neutral warm-gray/stone tones. Avoid
saturated multi-color UI — the palette is intentionally restrained.

## Fonts
- Body: a clean geometric sans-serif (system fallback: `ui-sans-serif, system-ui,
  sans-serif`)
- Headings/display: a distinct serif-adjacent or humanist display face for
  contrast against the sans body (system fallback: same sans stack if a custom
  font isn't available in the deploy environment)
- Font smoothing: antialiased on both WebKit and Mozilla
  ```css
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  ```

## Color tokens
```css
:root {
  --white: #ffffff;
  --night: #161714;        /* primary text / dark surfaces */
  --grape: #9677ff;        /* accent — primary CTA, links, highlights */
  --amethyst: #4e287a;     /* accent-hover — darker accent state */
  --ocean: #e5f8ff;        /* light tint background */
  --sky: #97c8ff;          /* secondary accent */
  --dusk: #6474cd;         /* secondary accent, muted */
  --raspberry: #985fca;    /* tertiary accent, sparing use */
  --gray: #81837a;         /* muted text */

  --midnight-25: #4a4b44;
  --midnight-50: #383a35;
  --midnight-75: #252622;
  --midnight-100: #21231e;

  --stone-25: #f7fbf5;     /* near-white surface */
  --stone-50: #e7ebe5;     /* card background */
  --stone-75: #d8dad1;     /* card hover */
  --stone-100: #c3c6bb;    /* borders, dividers */

  --sand-25: #f6f4f0;

  --background: var(--white);
  --foreground: var(--night);
  --accent: var(--grape);
  --accent-hover: var(--amethyst);
  --card: var(--stone-50);
  --card-hover: var(--stone-75);
  --border: var(--stone-50);
  --muted: color-mix(in srgb, var(--night) 60%, transparent);
}
```

## Usage rules
- **Background**: white (`--background`) as the default page surface.
- **Text**: `--night` for primary text; `--muted` (60% opacity night) for
  secondary/caption text.
- **Accent**: `--grape` for primary buttons, active states, links, and key
  metrics/highlights. Use `--accent-hover` (`--amethyst`) on hover/press states.
- **Cards/panels**: `--card` (stone-50) background, `--card-hover` (stone-75) on
  hover, `--border` (stone-50) for hairline borders — keep borders subtle, not
  heavy black lines.
- **Secondary accents** (`--sky`, `--dusk`, `--raspberry`) are for chart series,
  status badges, or secondary data viz — never for primary CTAs.
- Don't introduce colors outside this palette without a specific reason.

## Type scale
```css
--text-xs: 0.75rem;    /* line-height: 1/0.75 */
--text-sm: 0.875rem;   /* line-height: 1.25/0.875 */
--text-base: 1rem;     /* line-height: 1.5/1 */
--text-lg: 1.125rem;   /* line-height: 1.75/1.125 */
```
Font weights: 400 (normal), 500 (medium), 600 (semibold), 700 (bold). Prefer
500/600 for emphasis over jumping straight to 700 — the style reads as
confident rather than shouty.

Letter-spacing: `-0.025em` (tight) on large display text, `0.025em` (wide) on
small uppercase labels/eyebrows.

## Shape & spacing
```css
--radius-xs: 0.125rem;
--radius-sm: 0.25rem;
--radius-md: 0.375rem;
--radius-lg: 0.5rem;
--radius-xl: 0.75rem;
--radius-2xl: 1rem;
--spacing: 0.25rem;   /* base spacing unit — use multiples of this */
```
Default to `--radius-lg`/`--radius-xl` on cards and buttons — soft, not sharp,
but not pill-shaped either.

## Motion
```css
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--default-transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
```
Keep transitions short (150–250ms) and only on hover/state changes — no
decorative animation on a data/demo app.

## Applying this in a Streamlit app
Streamlit doesn't accept raw CSS variables in its native components, so:
1. Inject the token block above inside `st.markdown("<style>...</style>",
   unsafe_allow_html=True)` once, near the top of `app.py`.
2. Style custom HTML blocks (metric cards, scenario headers) directly with
   these tokens via `st.markdown` + inline HTML/CSS.
3. For native Streamlit widgets (buttons, metrics) that can't be fully
   restyled, at minimum override `theme` in `.streamlit/config.toml`:
   ```toml
   [theme]
   primaryColor = "#9677ff"
   backgroundColor = "#ffffff"
   secondaryBackgroundColor = "#e7ebe5"
   textColor = "#161714"
   font = "sans serif"
   ```
   This gets native widgets (buttons, sliders, dataframes) reasonably close to
   the palette without fighting Streamlit's rendering.
