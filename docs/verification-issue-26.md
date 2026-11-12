# Issue #26 (NFR-7 portability) - verification record

Date: 2026-11-12
Branch: feature/issue-26-portability

## What was checked and how

### 1. Operating systems (Windows / Linux / macOS)

CI (`.github/workflows/ci.yml`) runs the full Django test suite on SQLite on
`ubuntu-latest`, `windows-latest` and `macos-latest`, each with Python 3.10
and 3.12 (6 jobs). PostgreSQL runs in its own Ubuntu-only job because
GitHub-hosted service containers require Linux. Passing CI on the branch is
the OS evidence; no manual testing was done on physical Windows or macOS
machines.

### 2. Browsers (Chrome / Firefox) and mobile width

`scripts/browser_sweep.py` (committed alongside this record) opened the 14
main routes (8 admin, 6 student - HTTP status, JS console errors, and
page-level horizontal overflow at 1280px and 390px widths). This is
route-level HTTP/JS/layout coverage, not full workflow coverage of every
page state.

Run on 2026-11-12 against the final branch code, demo seed data only:

- Chrome Headless Shell 158.0.8127.18 (Playwright Chromium): 28/28 checks passed
- Firefox 159.0 (Playwright): 28/28 checks passed
- 56 page checks total, 0 failures (all HTTP 200, zero console errors,
  scrollWidth == viewport width at 390px on every page)

### 3. The mobile bug found and fixed

At 390px width Chrome showed page-level horizontal scrolling on the
complaints admin list, student complaints list and fee list. Root cause: the
absolutely positioned `.visually-hidden` "Actions" span in the table header
extended the page's scrollable overflow area outside the table's own
`overflow-x: auto` wrapper.

First attempt (`aria-label` on an empty `<th>`) fixed the overflow but
axe-core 4.10.2 flagged it under `empty-table-header` (a header cell with no
text content), so it was replaced: the visually-hidden span is back inside
the header cell, and the cell gets `position: relative` so the span is
contained inside the scroll wrapper. Re-verified:

- No horizontal overflow at 390px in Chrome and Firefox (all three pages,
  plus the full 56-check sweep above)
- axe-core 4.10.2 run against the tables: zero `empty-table-header`
  violations (screen readers still get the "Actions" header text)

### 4. Test suite

- complaints (60 tests) and fees (59 tests): OK after the template change
- Local integration check: merging `feature/sprint3-visitors-room-tags-error-pages`
  (PR #57) into this branch merges with no conflicts; the combined tree keeps
  both the Room column (#49) and this header fix, and the combined
  complaints/fees/visitors/accounts suite (223 tests) passes. Whichever PR
  lands second should re-run CI, but no manual conflict resolution is
  expected.

## Reproducing

```
pip install playwright && playwright install chromium firefox
python manage.py runserver 127.0.0.1:8000 &
HMS_ADMIN_USER=<demo admin> HMS_ADMIN_PASS=<demo pass> \
HMS_STUDENT_USER=<demo student> HMS_STUDENT_PASS=<demo pass> \
    python scripts/browser_sweep.py
```

Use demo/seed credentials only. The script exits non-zero on any failure
and prints the per-page results as JSON.
