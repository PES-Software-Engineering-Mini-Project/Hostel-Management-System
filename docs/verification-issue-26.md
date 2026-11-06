# Verification: NFR-7 portability (issue #26)

**Requirement.** SRS 6.4 Portability: runs on Windows, Linux and macOS with Python 3.10+, installed from one
`requirements.txt`, and works in current Chrome and Firefox. SAD 4.5: stays usable at 360 px width.

## What was added

- **CI** (`.github/workflows/ci.yml`, job `test-os`): the SQLite suite on `windows-latest` and `macos-latest`,
  each on Python 3.10 and 3.12. The existing Ubuntu job (SQLite and PostgreSQL) is unchanged.
- **`scripts/browser_sweep.py`**: a Playwright sweep of every main page as an anonymous user, an admin and a
  student who holds a room, in Chromium and Firefox at 360 px and 1280 px.

## How to run the sweep

One-time install (Playwright is not in `requirements.txt`, so CI and deployment stay small):

```bash
pip install playwright
playwright install chromium firefox
# Linux only, if a browser fails to start (needs sudo): playwright install-deps
```

Then, from the repository root:

```bash
python manage.py migrate
python scripts/browser_sweep.py
```

The script runs `seed_demo`, creates two sweep accounts (admin `PES1UG23SW001`, student `PES1UG23SW002` with a
room, a complaint, a fee record and a visitor), starts its own `runserver` on a free port and stops it at the
end. It writes to the configured database (`db.sqlite3` by default), so use a development database. Exit code
is 0 only when every check passes. Options: `--browsers chromium`, `--widths 360`, `--base-url http://...`.

Per page it checks: HTTP 200, no console errors or uncaught page errors, and no horizontal page scroll
(`document.documentElement.scrollWidth` not wider than the viewport). A table inside its own scrolling wrapper
is fine; the page itself must not scroll sideways.

## Pages covered (26, per browser and width)

- **Anonymous (2):** login, register.
- **Admin (16):** dashboard, rooms, add block, add room, pending applications, allocations, fees, add fee,
  complaints, students, student edit, reports index, 3 report pages, **visitor log (`/visitors/manage/`)**.
- **Student (8):** dashboard, my fees, my complaints, raise complaint, complaint detail, profile,
  **my visitors (`/visitors/`)**, **register visitor (`/visitors/new/`)**.

## Result

Run on a throwaway merge of the four Sprint 3 branches on top of `main`
(`#27` 18ea817, `#49` 2c85a69, `#5` a61f2f9, `#26` cb6b11a), with demo data from `seed_demo`.
Chromium and Firefox are the Playwright builds (Chromium for Chrome, Firefox 159), on Linux.

| Browser | Width | Role | Pages | Failed |
|---|---|---|---|---|
| Chromium | 360 px | anonymous | 2 | 0 |
| Chromium | 360 px | admin | 16 | 0 |
| Chromium | 360 px | student | 8 | 0 |
| Chromium | 1280 px | anonymous | 2 | 0 |
| Chromium | 1280 px | admin | 16 | 0 |
| Chromium | 1280 px | student | 8 | 0 |
| Firefox | 360 px | anonymous | 2 | 0 |
| Firefox | 360 px | admin | 16 | 0 |
| Firefox | 360 px | student | 8 | 0 |
| Firefox | 1280 px | anonymous | 2 | 0 |
| Firefox | 1280 px | admin | 16 | 0 |
| Firefox | 1280 px | student | 8 | 0 |

**104 checks, 0 failed.**

## Problems the sweep found and how they were fixed

First run: 3 failures, all in Chromium at 360 px (Firefox did not show them).

| Page | Problem | Fix |
|---|---|---|
| Admin fees list | Page scrolled sideways (911 px wide) | `.fee-table-wrap { position: relative }` in `fees.css` (#26) |
| Admin complaints list | Page scrolled sideways (878 px wide) | same, in `complaints.css` (#26) |
| My complaints | Page scrolled sideways (590 px wide) | same, in `complaints.css` (#26) |

**Cause.** The tables sit inside an `overflow-x: auto` wrapper, but the last header cell holds a
`.visually-hidden` span (`position: absolute`). With no positioned ancestor, Chromium places it against the
page, at the far right end of the table, and that widens the whole page. Making the wrapper `position:
relative` keeps the span inside the scroll area.

The visitor tables (#5) used the same markup but had no `.visually-hidden` rule at all, so the word "Actions"
was visible in the header. The sweep did not catch that, since it is not an overflow. It was fixed on the #5
branch (`a61f2f9`): the rule is defined and the wrapper is `position: relative`.

After the fixes, the second run passed everything above.

## Not verified here

- **Windows and macOS CI** only runs after the branch is pushed. The sweep itself was run on Linux only.
- Safari, real phones, and widths between 360 and 1280 px.
- The sweep checks overflow, status codes and console errors. It does not judge whether a page looks good.
- PostgreSQL is covered by the existing Ubuntu CI job, not by the sweep.

## Things that could still fail on Windows or macOS CI

- **Time zones.** `TIME_ZONE = "Asia/Kolkata"`. Python needs the `tzdata` package on Windows; Django 5.x pulls
  it in automatically on Windows (checked in its package metadata). Tests that compare dates near midnight could
  differ between the runner's clock and Asia/Kolkata.
- **Line endings.** There is no `.gitattributes`. A Windows checkout may use CRLF. `test_maintainability.py`
  reads source with `read_text`, which normalises newlines, and `utf-8-sig`, so it should be fine. The check for
  `"python manage.py test --verbosity 2\n"` in `ci.yml` is the one to watch.
- **Paths.** The code and tests use `pathlib`. The `.venv` exclusion in `test_maintainability.py` checks path
  parts, which works with Windows separators, but it has not run on Windows yet.
- **Shell.** The Windows job uses the default PowerShell. The CI steps are single-line commands, so this should
  not matter.
- **SQLite versions.** macOS and Windows runners ship different SQLite builds. The suite uses plain ORM queries
  with no SQLite-specific features, but this is also unproven until the run.
- **Python 3.10** is the oldest version in the matrix. The sweep script is only run locally, not in CI.
