# Config Page, README, and Frontend Cleanup — Implementation Plan

> **Status: COMPLETE** — All 6 tasks implemented on 2026-04-12.

**Goal:** Complete the broken config page, add a project README, and extract all inline CSS/JS to separate static files.

**Architecture:** Three independent workstreams that touch different files. Config page changes span backend + frontend. README is standalone. Frontend cleanup is pure refactor — extract inline code to files, verify no regressions.

**Tech Stack:** Python/Flask, vanilla JS, HTML/CSS, SQLite, pytest

---

## Commits

| SHA | Description |
|-----|-------------|
| `a140b30` | feat: complete config endpoint — all 4 radio fields with DB upsert |
| `c6421d2` | feat: config page sends all 4 radio fields, add nav link |
| `cc3d93e` | refactor: extract inline CSS to separate static files |
| `95e5538` | refactor: extract inline JS to separate static files |
| `3cea8ca` | docs: add project README with architecture and setup guide |
| `99838e6` | fix: config page supports both Radio 0 and Radio 1 |

## Results

- **155 tests passing** (7 new for config API)
- **0 inline `<style>` or `<script>` blocks** remaining in templates
- **1,010 lines** of CSS/JS extracted to static files

---

## File Map

**Created:**
- `webapp/static/css/base.css` — extracted from `base.html`
- `webapp/static/css/dashboard.css` — extracted from `dashboard.html`
- `webapp/static/css/satellite.css` — extracted from `satellite.html`
- `webapp/static/js/dashboard.js` — extracted from `dashboard.html`
- `webapp/static/js/satellite.js` — extracted from `satellite.html`
- `webapp/static/js/config.js` — radio selector + form handler for both R0/R1
- `README.md` — project documentation
- `tests/test_config_api.py` — 7 tests for config endpoint

**Modified:**
- `webapp/app.py` — `config_page` route (loads both radios), `api_config_update` (accepts radio field, upserts per-radio)
- `webapp/templates/config.html` — radio selector dropdown, loads configs via `tojson`
- `webapp/templates/base.html` — `<style>` → CSS link, added Config nav link
- `webapp/templates/dashboard.html` — `<style>` → CSS link, inline `<script>` → JS file
- `webapp/templates/satellite.html` — `<style>` → CSS link, inline `<script>` → JS file
- `tests/test_vuln_cmdi.py` — response key `output` → `shell_output`
- `tests/test_full_vulns.py` — response key `output` → `shell_output`

---

### Task 1: Config Page — Backend (all 4 fields + DB upsert) [DONE]

**Files:**
- Created: `tests/test_config_api.py`
- Modified: `webapp/app.py:201-265`

- [x] **Step 1: Write failing tests** — 5 tests for the updated config endpoint
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement updated endpoint** — accepts frequency, spreading_factor, bandwidth, tx_power; passes all through f-string shell command (GS-07); upserts radio_config with `safe_int()` for DB storage
- [x] **Step 4: Run tests to verify they pass** — 5/5 pass
- [x] **Step 5: Run full test suite** — 153 pass (fixed `test_vuln_cmdi.py` and `test_full_vulns.py` for response key change `output` → `shell_output`)
- [x] **Step 6: Commit** — `a140b30`

---

### Task 2: Config Page — Frontend (send all 4 fields + nav link) [DONE]

**Files:**
- Created: `webapp/static/js/config.js`
- Modified: `webapp/templates/config.html`, `webapp/templates/base.html`

- [x] **Step 1: Create config.js** — form submit handler sends all 4 fields
- [x] **Step 2: Update config.html** — external script reference, removed inline JS
- [x] **Step 3: Add Config link to nav** — `base.html` nav bar
- [x] **Step 4: Run tests** — 153 pass
- [x] **Step 5: Commit** — `c6421d2`

---

### Task 3: Frontend Cleanup — Extract CSS [DONE]

**Files:**
- Created: `webapp/static/css/base.css` (11 lines), `dashboard.css` (49 lines), `satellite.css` (28 lines)
- Modified: `webapp/templates/base.html`, `dashboard.html`, `satellite.html`

- [x] **Step 1: Create base.css** — extracted from `base.html <style>`
- [x] **Step 2: Create dashboard.css** — extracted from `dashboard.html <style>`
- [x] **Step 3: Create satellite.css** — extracted from `satellite.html <style>`
- [x] **Step 4: Update base.html** — `<style>` → `<link rel="stylesheet">`
- [x] **Step 5: Update dashboard.html** — `<style>` → `<link>`, kept socket.io CDN
- [x] **Step 6: Update satellite.html** — `<style>` → `<link>`
- [x] **Step 7: Run tests** — 153 pass
- [x] **Step 8: Commit** — `cc3d93e`

---

### Task 4: Frontend Cleanup — Extract JS [DONE]

**Files:**
- Created: `webapp/static/js/dashboard.js` (187 lines), `satellite.js` (393 lines)
- Modified: `webapp/templates/dashboard.html`, `satellite.html`

- [x] **Step 1: Create dashboard.js** — verbatim extraction of inline script (hardware control, TC form, status polling)
- [x] **Step 2: Create satellite.js** — verbatim extraction (~400 lines: polling loop, battery, sensors, LoRa, controls)
- [x] **Step 3: Update dashboard.html** — inline `<script>` → `<script src="dashboard.js">` + `<script src="telemetry.js">`
- [x] **Step 4: Update satellite.html** — inline `<script>` → `<script src="satellite.js">`
- [x] **Step 5: Run tests** — 153 pass
- [x] **Step 6: Commit** — `95e5538`

---

### Task 5: README [DONE]

**Files:**
- Created: `README.md` (115 lines)

- [x] **Step 1: Write README** — requirements, installation, simulated/hardware modes, architecture tables (core + webapp modules), webapp pages, test instructions, directory structure
- [x] **Step 2: Run tests** — 153 pass
- [x] **Step 3: Commit** — `3cea8ca`

---

### Task 6: Final Verification [DONE]

- [x] **Step 1: Run full test suite** — 155 passed
- [x] **Step 2: Verify no inline styles/scripts** — `grep '<style>'` and `grep '<script>' | grep -v src=` return no results
- [x] **Step 3: Spot-check file sizes** — base.css:11, dashboard.css:49, satellite.css:28, config.js:15→34, dashboard.js:187, satellite.js:393, telemetry.js:327

---

### Post-Plan Fix: Dual-Radio Config [DONE]

After testing, the config page only showed one radio. Fixed by:

- Added radio selector dropdown (Radio 0 / Radio 1) to `config.html`
- Backend `api_config_update` accepts `radio` field, upserts per-radio description
- `config_page` route loads all configs for user, passes as dict to template
- `config.js` populates form fields on radio change, caches updates locally
- Added 2 new tests: `test_config_update_radio1`, `test_config_page_renders_both_radios`
- Commit: `99838e6`
