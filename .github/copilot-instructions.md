# Copilot Instructions

## Project Overview

A **Promotion Readiness Dashboard** — a self-contained HTML+JS app for tracking employee development and career advancement. No framework or build step; all logic lives in `development_plan.html`. Python scripts handle persistence and markdown snapshot generation.

## Running Locally

```bash
# Serverless (open directly in Chrome/Edge — recommended)
open development_plan.html

# With local server (auto-injects data.json into page, regenerates MD on save)
python3 serve.py
# → http://localhost:7654/
```

There are no tests or linters.

## Architecture

```
development_plan.html   ← single-file app: all HTML, CSS (~380 lines), and JS (~700 lines)
data.json               ← authoritative state file (written by FSA or serve.py POST /save)
development_plan.md     ← auto-generated snapshot; never edit manually
generate_md.py          ← reads data.json → writes development_plan.md (uses BeautifulSoup4)
serve.py                ← dev server on :7654; injects data.json into HTML on GET, calls generate_md.py on POST /save
.git/hooks/pre-commit   ← runs generate_md.py && git add development_plan.md before every commit
```

## State Management

All dashboard state is collected into a single JS object by `collectState()` and restored by `applyState()`. The state object shape matches `data.json`:

```js
{
  ver: 5,          // bump when state schema changes (applyState rejects mismatched versions)
  ts: "<ISO>",
  dims: [{ id, label }],
  employee, manager, period, curLevel, tgtLevel, revDate,
  actionHTML: "<serialized tbody innerHTML>",
  notesHTML:  "<serialized tbody innerHTML>"
}
```

`STORE_KEY` and `STORE_VER` (defined near the top of the `<script>`) must stay in sync with `data.json`'s `ver` field. Incrementing `STORE_VER` invalidates all localStorage/FSA-stored states.

**Save priority chain (auto-save + manual save):**
1. FSA API (`_fsaWrite`) — direct file write if user connected `data.json` via "Connect data.json" or "🔄 Load from JSON"
2. `localStorage` — always written as fallback
3. Browser download of `data.json` — only on manual "💾 Save & Update" when no FSA handle

**Restore priority chain (on page load):**
1. FSA handle cached in IndexedDB (`_cachedFH`)
2. `<script id="_initial_data">` tag injected by `serve.py`
3. `localStorage`

## Key JS Conventions

**DOM is the source of truth for content.** State is serialized as HTML fragments (`actionHTML`, `notesHTML`). `collectState()` clones the live tables and syncs input/textarea/select values into clone attributes before serializing `innerHTML`. `applyState()` sets `innerHTML` directly.

**Badge cycling** (`cycleBadge(el)`): click any `.badge` to advance it through its cycle. Cycles are defined in `badgeCycles` keyed by type (`status`, `priority`, `type`, `note_type`). CSS class (`badge-red`, `badge-orange`, `badge-blue`, `badge-green`, `badge-grey`) is derived from the new value.

**Computed UI** (`buildOverview()`): scans `#action-body` on every change, aggregates stats per dimension, updates `#dimensions-body`, dial, and KPI cards. Always call `buildOverview()` after modifying action rows programmatically.

**Auto-save** is debounced 1500 ms via `scheduleAutoSave()`. Call this (not `saveState()` directly) after any user-driven change.

**Auto-log** (`autoLog(msg)`): appends change events to a same-day `<tr class="auto-log-row">` in `#notes-body`. Triggered automatically by `cycleBadge` and dimension changes.

**Subtask rows** (`.subtask-row`) must always immediately follow their parent action row in the DOM. `syncParentFromSubtasks()` derives parent status/due/priority from children.

## HTML Structure

```
<div class="header">   ← employee / manager / period (contenteditable spans)
<div class="nav">      ← tab buttons + save controls
<div class="main">
  <div id="overview" class="section active">
  <div id="actions"  class="section">
  <div id="notes"    class="section">
<script id="_initial_data" type="application/json">  ← injected by serve.py; parsed in restoreState()
<script>  ← all application logic
```

Sections are shown/hidden by toggling `.active`. Never add `display` styles directly to `.section` elements.

## generate_md.py

Parses `actionHTML` and `notesHTML` with BeautifulSoup. It skips rows with class `subtask-row` or `subtask-add-row`. Column indices in `action_rows` parsing are positional (0–8) — if columns are added/reordered in the HTML table, update the index mapping in `generate_md.py` accordingly.

`STATUS_PCT` in `generate_md.py` must mirror `statusToPct` in the JS.
