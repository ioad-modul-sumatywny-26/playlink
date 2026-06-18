# Frontend Component Library

The Playlink frontend bundles a small set of domain-specific components (`GameManager`, `MnemonicInput`, `RoomEvent`) and an 18-piece chrome UI kit — a Diablo-II-themed widget library. All components use Svelte 5 runes conventions: `$props()` for prop declarations, `$bindable()` for two-way-bound state, `$state`/`$derived`/`$effect` for local reactivity, and `{@render children?.()}` for snippet/children slots.

> **Source:** `frontend/src/lib/components/GameManager.svelte`, `MnemonicInput.svelte`, `RoomEvent.svelte`, `frontend/src/lib/components/chrome/*.svelte`

Shared design tokens and component styling live in `frontend/src/lib/styles/tokens.css` (CSS custom properties for colours, typography, spacing) and `frontend/src/lib/styles/chrome.css` (bevel/etched/small-caps atomic classes). `frontend/src/lib/global.css` provides the CSS reset, font declarations (Exocet display, Cinzel mono), and Diablo II cursor images. These files are imported by the root layout — individual components do not import them directly.

---

## Domain Components

### GameManager

Admin-only dialog for creating and deleting custom game categories. POSTs `?/addGame` and `?/deleteGame` form actions via `fetch` + `deserialize`.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `open` | `boolean` | — | yes | Dialog visibility |
| `games` | `string[]` | — | no | Current game category list |
| `onclose` | `() => void` | — | no | Called when dialog closes |

The component wraps a `SystemDialog` with `tone="gold"` `modal` `width="520px"`. Internal state tracks a new-game name input, a `feedback` message (type `'success' | 'error'`), a `busy` flag, and a `conflict` object.

**Delete conflict flow:**
1. `deleteGame(game)` sends `?/deleteGame` with `name`.
2. If the backend returns `{ type: 'failure', data: { conflict: true, error: "…" } }`, the conflict UI appears showing a "Force Delete" button and a "Cancel" link.
3. "Force Delete" calls `deleteGame(game, true)`, which appends `force: 'true'` to the form data.
4. On success, `invalidateAll()` triggers a re-fetch of the route data.

**Keyboard:** The name input accepts Enter key to trigger `addGame()` (via `onAddKey`).

See [routes](routes.md) for the `?/addGame` and `?/deleteGame` action implementations in `rooms/+page.server.ts`.

---

### MnemonicInput

A 12-word BIP39 mnemonic entry grid. Three columns of four slots, each showing a numbered input with per-word BIP39 dictionary validation via `ethers.wordlists.en.getWordIndex()`. Words are tracked as a `string[]` of 12 entries and synchronised with the bindable `value` (a space-joined string).

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `value` | `string` | — | yes | Space-joined 12-word phrase |

**Bidirectional sync:**
- **Parent → child:** An `$effect` watches `value`. When it becomes a 12-word string, `words` is updated (only if the external value differs from the current internal state). When `value` clears, all slots reset.
- **Child → parent:** An `$effect` joins `words` on space and sets `value`.

**Navigation:**
- `Space` / `Enter` / `Tab` → advance to next slot.
- `Backspace` on an empty slot → move to previous slot.
- `Paste` → splits on whitespace, fills up to 12 slots, lowercase-strips non-alpha characters.

**Validation per slot:**
- If non-empty and `wordlist.getWordIndex(word) === -1`, the slot gets class `invalid` (red tint).
- If valid, class `valid-filled` (green tint) and a `▸` marker appear.

Used on the `/auth` route; see [routes](routes.md).

---

### RoomEvent

Scheduling and RSVP panel for a room event. Displays countdown, roster of RSVPs, and (for creator) edit/cancel controls; for members, RSVP buttons.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `event` | `RoomEventState \| null` | — | no | Current event data, or `null` if unscheduled |
| `isCreator` | `boolean` | — | no | Viewer owns the room |
| `isMember` | `boolean` | — | no | Viewer is a room member |
| `viewerAddress` | `string` | — | no | Viewer's Ethereum address (lowercased internally) |
| `members` | `{ address: string; username?: string }[]` | — | no | All room members |
| `formError` | `string \| null` | `null` | no | Server-side error from the parent form |

**States:**
1. **No event, is creator** — "Schedule Event" button, toggles editing mode.
2. **No event, not creator** — "No event scheduled yet" message.
3. **Event scheduled, not editing** — Shows start/end time (formatted via `Intl.DateTimeFormat`), countdown timer, RSVP controls (if member), and roster.
4. **Editing** — `D2DatePicker` + `D2TimePicker` for start and end. On submit, validates local constraints then posts to `?/scheduleEvent`.

**Countdown** (updates every 1s via `setInterval`):
- Before start: `STARTS IN [d HH:MM:SS]`
- During: `IN PROGRESS — [HH:MM:SS] LEFT`
- After end: `ENDED`

**RSVP:** Three buttons per member: Present ✓, Absent ✗, Maybe ?. Each POSTs `?/setRsvp` with `status`. The roster merges `event.rsvps` with `members` (addresses not in `rsvps` show "No Response").

**Editing form validation** (`validateDraft`):
- Start and end dates must be set.
- End must be after start.
- Start must be in the future.

Cross-links: uses `D2DatePicker` and `D2TimePicker` (see Chrome UI Kit below). `RoomEventState`, `RsvpEntry`, `RsvpStatus` types come from [chatStore](../frontend/library.md). The form action `?/scheduleEvent` / `?/cancelEvent` / `?/setRsvp` is documented in [routes](routes.md).

---

## Chrome UI Kit

The chrome kit provides 18 Diablo-II-themed widgets. All components accept `children?: import('svelte').Snippet` where noted, and use `$props()` with TypeScript `interface Props`.

### Cycler (generic `<T>`)

Cycles through an array of values with chevron buttons. Wraps around at boundaries.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `values` | `T[]` | — | no | Item pool |
| `value` | `T` | — | yes | Currently selected value |
| `label` | `string \| undefined` | — | no | Optional label text |
| `format` | `(v: T) => string` | — | no | Custom display formatter |
| `disabled` | `boolean` | `false` | no | Disables navigation |
| `onchange` | `(v: T) => void` | — | no | Called with the new value on change |

Uses `$effect` to initialise `value` to `values[0]` if undefined. Left/right chevron buttons pulse on click for 120ms.

### Crest

An SVG Diablo-II-style shield crest with Celtic knotwork, compass-star, and rivets.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `size` | `number` | `96` | no | Width/height in px |
| `tone` | `'gold' \| 'bone' \| 'iron'` | `'gold'` | no | Colour variant |

Rendered as `<span aria-hidden="true" role="presentation">` with inline SVG.

### D2DatePicker

Popover calendar date picker with a 42-cell (6×7) grid, month navigation, and auto-placement.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `value` | `Date \| null` | — | no | Currently selected date |
| `onChange` | `(d: Date) => void` | — | no | Called when a date is picked (preserves existing time-of-day) |
| `min` | `Date \| null` | `null` | no | Minimum selectable date |
| `placeholder` | `string` | `'Pick a date'` | no | Text when no date selected |
| `ariaLabel` | `string` | `'Date'` | no | Trigger button aria-label |

**Behaviour:**
- Weekday header starts on Monday.
- Popover auto-flips above when space below is < 320px.
- Clicking a non-current-month cell navigates to that month.
- "Today" button in the header row (`onclick: jumpToday()`).
- Closes on outside click and Escape.
- Four bronze rivets in popover corners (matching InnerPanel aesthetic).

### D2TimePicker

Popover time picker with two scrollable columns (hours 00–23, minutes at chosen granularity).

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `value` | `string` | — | no | Current time as `"HH:MM"` (24h) |
| `onChange` | `(value: string) => void` | — | no | Called on pick with `"HH:MM"` |
| `step` | `5 \| 10 \| 15 \| 30` | `5` | no | Minute picker granularity |
| `ariaLabel` | `string` | `'Time'` | no | Trigger button aria-label |

**Behaviour:**
- Parses `value` as `HH:MM`; falls back to `18:00` on parse failure.
- Selected hour/minute scrolls into view on open.
- Closes on outside click and Escape.

### Hint

A keyboard-hint badge showing a key + label pair.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `key` | `string` | — | no | Key glyph (e.g. `"E"`, `"⏎"`, `"M"`) |
| `label` | `string` | — | no | Description text |
| `tone` | `'gold' \| 'green' \| 'amber' \| 'red' \| 'stone' \| 'blue'` | `'stone'` | no | Colour accent |
| `onclick` | `() => void` | — | no | If set, renders as `<button>`; else as `<span>` |

The `tone` type (`HintTone`) is shared with [hintsContext](../frontend/library.md). Most routes push `HintEntry[]` via `provideHints()` / `getHintsState()`.

### HintBar

Footer bar for keyboard hints. Renders a gold rule and a flex row of children. Hidden on touch devices via `@media (hover: none) and (pointer: coarse)`.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `children` | `Snippet` | — | no | Hint elements (typically `Hint` components) |

Rendered as `<footer aria-label="Keyboard hints">`.

### InnerPanel

A stone-slab panel with bronze frame, four rivets, and CSS stone grain noise.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `title` | `string \| undefined` | — | no | Optional panel heading (etched gold, small-caps) |
| `padded` | `boolean` | `true` | no | Inner padding |
| `children` | `Snippet` | — | no | Panel body content |
| `actions` | `Snippet` | — | no | Actions rendered beside title in header |

When `title` or `actions` is present, a header row with a gold rule is rendered above the body. The stone grain is a CSS pseudo-element with layered noise.

### ListRow

A grid row with multiple states used for room/member lists.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `selected` | `boolean` | `false` | no | Selected state (shows gold pip) |
| `header` | `boolean` | `false` | no | Header row (no interaction, no pip) |
| `disabled` | `boolean` | `false` | no | Disabled state |
| `member` | `boolean` | `false` | no | Member state (shows dim pip) |
| `onclick` | `() => void` | — | no | Click handler; makes row interactive |
| `children` | `Snippet` | — | no | Row content |

**Interaction:** If `!header && !disabled && typeof onclick === 'function'`, the row has `role="button"`, `tabindex="0"`, and responds to Enter/Space. Clicking fires a 180ms pulse animation. `aria-selected` and `aria-disabled` are set automatically.

### OrnateButton

Themed button or link with multiple variants and sizes.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `variant` | `'primary' \| 'secondary' \| 'danger' \| 'ghost'` | `'secondary'` | no | Visual style |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | no | Button size |
| `type` | `'button' \| 'submit' \| 'reset'` | `'button'` | no | Button type (ignored when `href` set) |
| `disabled` | `boolean` | `false` | no | Disabled state |
| `loading` | `boolean` | `false` | no | Loading state (also disables) |
| `href` | `string \| undefined` | — | no | If set, renders `<a>` instead of `<button>` |
| `fullWidth` | `boolean` | `false` | no | Stretches to container width |
| `onclick` | `(e: MouseEvent) => void` | — | no | Click handler |
| `children` | `Snippet` | — | no | Button/link label |

When `href` is set, renders as `<a role="button">` with `aria-disabled`. When `loading`, the inner span shows a pulsing slot animation (the `ornate__inner` div shifts in a CSS loop). `fullWidth` applies `width: 100%` via a class.

### PageFrame

Top-level layout frame: stone wall backdrop with quatrefoil pattern, vignette overlay, four corner SVG shield ornaments, and gold edge hairlines.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `children` | `Snippet` | — | no | Page content |

Rendered as `<div class="page-frame anim-frame-in">`. The frame-back layer adds a warm-dark-brown stone wall with CSS quatrefoil repeating pattern and a radial vignette darkening the edges. Four `<svg>` corner pieces in the frame-chrome layer use a gold-gradient stroke. Four `<span>` hairline edges (top/bottom/left/right) complete the frame. Content sits inside `.frame-inner`.

### PipMeter

Pip indicator — a row of orbs showing a count with colour per tone.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `value` | `number` | — | no | Numeric value (floored to integer for lit pips) |
| `total` | `number` | `3` | no | Total pip count |
| `tone` | `'good' \| 'mid' \| 'bad' \| 'auto'` | `'auto'` | no | Colour scheme |
| `size` | `'sm' \| 'md'` | `'md'` | no | Pip size |
| `glow` | `boolean` | `true` | no | Outer glow on lit pips |
| `label` | `string \| undefined` | — | no | Text label below pips |

**Auto-tone** (when `tone = 'auto'`):
- lit ≥ 3 → `good` (green)
- lit = 2 → `mid` (amber)
- lit = 1 → `bad` (red)
- lit = 0 → `good` (default)

Lit pips animate with a scale-and-brightness pop keyframe (`orbPop` 300ms) when they transition from unlit to lit.

### ProgressBar

Horizontal progress bar with optional tick marks and label.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `value` | `number` | — | no | Current value |
| `max` | `number` | `100` | no | Maximum value |
| `height` | `number` | `6` | no | Fill height in px |
| `ticks` | `boolean` | `false` | no | Show 25%/50%/75% tick marks |
| `variant` | `'gold' \| 'blood' \| 'green'` | `'gold'` | no | Fill colour |
| `label` | `string \| undefined` | — | no | Label text + numeric counter |

The fill width is `clamped / safeMax * 100%` with a smooth `transition: width 0.35s ease`. `safeMax` ensures `max <= 0` becomes 1. The `progressbar` ARIA role and `aria-valuenow`/`aria-valuemax` are set.

### SectionTitle

Section heading with a title, gold rule, and optional trail slot.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `title` | `string` | — | no | Heading text |
| `size` | `'small' \| 'normal' \| 'large'` | `'normal'` | no | Font size tier |
| `tone` | `'gold' \| 'bone' \| 'blood'` | `'gold'` | no | Title colour |
| `children` | `Snippet` | — | no | Content for the trail slot (right side of the rule) |

Renders `<h3 class="title small-caps">`. The rule is a flex-growing hairline `1px` background.

### Sigil

Deterministic SVG sigil generated from an Ethereum address.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `address` | `string` | — | no | Ethereum address (0x-prefixed) |
| `size` | `number` | `56` | no | Width/height in px |

**Generation algorithm (`parseSpec`):**
1. Lowercases the address, strips `0x` prefix.
2. Requires ≥ 12 hex characters; pads deterministically to 16 bytes.
3. `bytes[0] % 6` → shape index (0–5).
4. `bytes[1] % 3` → symmetry type: `0` = vertical mirror, `1` = 4-fold rotation, `2` = 3-fold rotation.
5. `bytes[10] % 2 === 1` → `useGold` for accent colour.
6. `bytes[11] & 0x0f` → accent ring selector.
7. 25 cells (5×5 grid) derived from `bytes[2..]` via `(bytes[2 + i*4] >> (i % 8)) & 1`, then folded by the chosen symmetry.

Rendered as `<div class="sigil-frame bevel-out" aria-hidden="true">` with an inner SVG. Invalid addresses produce a fallback crossed-swords icon (`X` pattern).

### StoneCheckbox

Diablo-II-themed checkbox with stone box and animated SVG checkmark.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `checked` | `boolean` | `false` | yes | Checked state |
| `label` | `string \| undefined` | — | no | Label text (small-caps) |
| `disabled` | `boolean` | `false` | no | Disabled state |
| `size` | `'sm' \| 'md'` | `'md'` | no | Checkbox size |
| `onchange` | `(checked: boolean) => void` | — | no | Called on toggle with new value |

A real `<input type="checkbox" class="sr-only">` is used for accessibility; the visual box is a `<span>` with an SVG checkmark that scales in on `checked`. The label is a `<label>` wrapping the input, so clicking the visual box toggles the state.

### SystemDialog

Modal, inline, or floating dialog with configurable tone, position, and footer slot.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `open` | `boolean` | `false` | yes | Dialog visibility |
| `title` | `string` | — | no | Dialog title |
| `tone` | `'gold' \| 'blood' \| 'green' \| 'iron'` | `'iron'` | no | Accent colour |
| `modal` | `boolean` | `false` | no | Dark overlay, Escape closes, body scroll locked |
| `inline` | `boolean` | `false` | no | Renders in-flow (no overlay) |
| `position` | `'bottom-right' \| 'top-center' \| 'center'` | `'bottom-right'` | no | Floating dialog position |
| `width` | `string` | `'420px'` | no | CSS width value |
| `closeable` | `boolean` | `true` | no | Permits closing; `false` hides close button and disables close |
| `onclose` | `() => void` | — | no | Called when dialog closes |
| `children` | `Snippet` | — | no | Dialog body content |
| `footer` | `Snippet` | — | no | Footer content (rendered below the body) |

**Four rendering modes:**
1. **Modal** (`modal: true`) — dark overlay, centering, body `overflow: hidden`, Escape closes.
2. **Inline** (`inline: true`) — no overlay, rendered in the normal document flow.
3. **Floating** (default) — positioned absolutely per `position` value.
4. **Hidden** (`open: false`) — renders nothing.

Tone controls the heading rule colour, close-button colour, and overlay tint via CSS classes. The dialog fires `onclose` when closed, setting `open = false`.

### Tab

Navigation tab for the top navigation bar. Uses `$app/state` page store for active detection.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `href` | `string` | — | no | Route path |
| `match` | `'exact' \| 'prefix'` | `'prefix'` | no | URL matching strategy |
| `label` | `string \| undefined` | — | no | Tab label text |
| `children` | `Snippet` | — | no | Alternative to `label` for custom content |

**Active detection:** When `match = 'prefix'`, the tab is active when `page.url.pathname === href` or starts with `href + '/'`. When `match = 'exact'`, only an exact match counts. Active tab shows a gold arrow indicator below the text. Uses `data-sveltekit-preload-data="hover"` for prefetching.

### Tabs

Tab bar container — renders children in a `grid-auto-flow: column` row with top and bottom gold rules.

| Prop | Type | Default | Bindable | Description |
|------|------|---------|----------|-------------|
| `children` | `Snippet` | — | no | Tab elements |

At ≤ 600px viewport width, the row becomes `overflow-x: auto` with hidden scrollbar. The top and bottom rules are gradient fades from transparent → gold → transparent.
