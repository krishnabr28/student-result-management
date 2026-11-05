# Student Result Management System

Flask + MySQL (raw parameterised SQL via `app/db.py`), Jinja templates, vanilla JS. Setup and run: see README.
Business rules live only in `app/rules.py`; the JS preview in `app.js` mirrors them but the server is authoritative.
Windows: `setup.bat` (scripts/windows-setup.ps1 + setup_helper.py) installs everything; `start.bat` runs the app. Keep .bat/.ps1 ASCII + CRLF and PowerShell 5.1 compatible.
Tests: `pytest` (needs MySQL from `.env`; uses a throwaway `srms_test` DB). Lint: `ruff check .`.

## Design System

- **Look:** calm, flat, Linear/Vercel-style glass. Dark is the default; light via `[data-theme="light"]` (localStorage
  `srms-theme`). No decorative gradients anywhere: no aurora, gradient text, buttons or bars. The only gradient is
  the student score ring: a hard-stop conic arc plus its ring mask.
- **Palette (neutral zinc, no blue tint):** dark bg #09090b, text #f4f4f5, muted #a1a1aa; light bg #f4f4f5, white
  panels, text #18181b, muted #52525b. ONE accent, deck orange `--color-accent #c2410c` (white label 5.2:1);
  accent text/focus #fb923c dark, #c2410c light. Accent only for the brand mark, primary button, focus, current
  filter chip, unread state and data bars. Active nav, stat icons, ranks and avatar stay neutral.
- **Tokens:** every colour, radius, shadow, spacing, duration and z-index lives in `app/static/css/tokens.css`.
  Components use tokens only; add a token rather than a raw value.
- **Radii:** 6 (small buttons, grade chips) · 8 (controls) · 12 (cards, menus, toasts) · 16 (dialog, login card);
  pills for badges and chips.
- **Type:** system stack (Inter if installed, no web fonts). Scale 11/12/14/16/18/21/28/36/48 px; headings weight
  600 with tight tracking; labels and table headers in sentence case (no all-caps); tabular numbers for marks.
- **Glass:** `.glass` = translucent bg + 20px blur + 180% saturate + 1px border + inset top highlight. Header uses
  `--glass-bg`; toasts and the dialog use `--glass-bg-elevated`; menus inside the header use near-opaque
  `--glass-bg-strong` (nested backdrop-filter cannot blur); the phone nav is solid. `.card` = 3% white (dark) or
  82% white (light) panel with a 1px border and hairline highlight, with almost no shadow. Solid fallbacks for no
  backdrop-filter, `prefers-reduced-transparency` and `prefers-contrast: more`.
- **Backdrop:** solid bg plus one faint neutral blurred shape at the top (`body::before`, `--backdrop-light`),
  hidden under reduced transparency or high contrast. It must never read as a colour wash.
- **Controls:** inputs use `--color-border-control` (3:1 against the card); secondary buttons are a raised surface
  with a 1px border; primary is flat accent with a 1px inner highlight.
- **Motion:** 120–250 ms, transform/opacity/colour only; durations zeroed under `prefers-reduced-motion`.
- **Status colours:** success = Pass, danger = Fail, warning = Pending; grade chips are neutral.
- **Responsive (checked at 320/360/390/414/768/1024/1280px, no sideways scroll):** nav icons hide under 1180px;
  nav collapses to a menu under 960px; `.table-cards` tables become stacked cards under 900px (two per row on
  tablets; each `td` needs `data-label`); header menus become full-width under 640px; inputs go to 16px under
  640px (no iOS zoom); brand text hides under 400px.
- **A11y:** AA contrast for every token pair, checked with a script that composites translucent tokens over the
  bg and card; visible focus ring; 40px+ targets; `sr-only` labels on icon buttons.
