# Design — The Lenny Growth Assistant

## 1. Information Architecture

Two top-level surfaces, no navigation chrome beyond them — the product is the conversation:

```
┌──────────────┬─────────────────────────────┬───────────────────────┐
│  Sessions     │   Chat pane                  │  Artifact pane        │
│  sidebar      │   (messages, composer)        │  (collapsible)        │
│  (collapsible │                               │                       │
│  on mobile)   │                               │                       │
└──────────────┴─────────────────────────────┴───────────────────────┘
```

- **Sessions sidebar** — list of past conversations by title + relative time, "New conversation" button.
  Collapses to a slide-over on mobile.
- **Chat pane** — message history, provider badge per assistant message, source citation cards under
  grounded answers, composer with a mode toggle (Ask / Ship 30 for 30) and provider selector.
- **Artifact pane** — opens automatically when a message produces an artifact; otherwise shows an empty
  state. Collapsible via a single control so the chat pane can go full-width.

## 2. Visual Language

The product's subject matter is *operator knowledge extracted from long-form audio* — the design should
feel like a research tool, not a generic chat toy. Direction: **editorial dark mode** — a deep
charcoal/ink background (not pure black), a warm amber accent standing in for "cited/grounded" moments
(distinct from the cooler neutral used for the AI's own voice), and a serif/sans pairing that nods to
"transcript" without literally rendering typewriter text everywhere.

- **Type:** `Fraunces` (or system serif fallback) for the app wordmark and section headers only; `Inter`
  for everything else (body, UI labels, chat text). Two families, clearly distinct roles — serif never
  appears in body copy.
- **Color:** ink background (`#12100E`), warm off-white text (`#F4EFE8`), amber accent (`#D98E39`) reserved
  specifically for citations/grounded badges so "this claim is sourced" has one consistent visual signal
  across the whole app, and a cool slate (`#5B6B79`) for secondary/meta text (timestamps, provider badges).
- **Chat bubbles:** user turns right-aligned, flat ink-on-amber-tinted surface; assistant turns
  left-aligned, subtle bordered card (not a filled bubble) so long grounded answers with citation cards
  underneath don't feel visually boxed-in.

## 3. Key Interaction States

| State | Treatment |
|---|---|
| Empty (new session) | Centered prompt suggestions drawn from real sample-transcript topics, not lorem-ipsum |
| Streaming | Assistant bubble shows a blinking-cursor caret at the end of the growing text; composer disabled with a "stop" affordance |
| Loading (retrieval) | A single inline status line ("Searching the archive…") replaces the empty assistant bubble before tokens start |
| Source citations | Small cards under the answer: episode title, guest, timestamp, similarity score as a subtle bar, click to expand the excerpt |
| Grounded refusal | Same visual treatment as a normal answer (not an error state) — it's a valid, expected outcome, styled with a neutral "no match" icon instead of the amber citation badge |
| Error (provider/DB down) | Inline banner in the chat pane, specific and actionable ("Ollama isn't reachable at localhost:11434 — start it, or switch to Claude"), never a raw stack trace |
| Artifact ready | Artifact pane auto-opens with a subtle slide-in; a matching reference chip appears in the chat message ("📄 Opened in artifact pane") instead of dumping raw markup into the chat |

## 4. Responsive Behavior

- **Desktop (≥1024px):** three-column layout as above, artifact pane defaults open when present.
- **Tablet (640–1023px):** sessions sidebar collapses behind a menu icon; chat + artifact remain
  side-by-side but narrower; artifact pane can be toggled full-screen.
- **Mobile (<640px):** single column. Chat is the default view; artifact pane becomes a full-screen
  sheet reachable via a "View artifact" button that appears on messages that produced one, rather than
  trying to show two panes at once.

## 5. Accessibility

- All interactive controls (send, provider toggle, mode toggle, session items, artifact collapse) are
  real `<button>`/`<a>` elements with visible focus rings (not `div onClick`).
- Color is never the only signal: the "grounded vs. refusal vs. error" states differ in icon and copy, not
  just badge color, for color-blind users.
- Streaming text updates use an `aria-live="polite"` region so screen readers announce new content without
  interrupting mid-sentence.
- Minimum contrast ratio 4.5:1 for body text against the ink background (verified for the palette above).
- Composer is keyboard-first: `Enter` sends, `Shift+Enter` newlines, `Esc` collapses the artifact pane.

## 6. Design Decisions Worth Calling Out

- **Citations as structured cards, not inline footnotes** — a growth PM skimming for a tactic needs to see
  *which guest said it* at a glance, not hunt for a `[1]` and scroll to a footnote.
- **Refusal is not styled as an error** — treating "the archive doesn't know" as a first-class, calmly
  presented state (rather than a red banner) reinforces trust that the assistant isn't guessing, which is
  the whole value proposition of a grounded tool.
- **Artifact pane is separate from the chat transcript** — mirrors the assignment's explicit ask ("similar
  in spirit to Claude Artifacts") and keeps generated deliverables (the actual thing a PM will paste into
  a doc) visually distinct from conversational exchange.
