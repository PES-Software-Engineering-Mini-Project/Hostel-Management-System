#!/usr/bin/env python3
"""Cross-browser smoke sweep for the HMS pages (issue #26, NFR-7).

Opens every main page in Chromium and Firefox, at desktop (1280px) and
mobile (390px) widths, and checks for each page:

- HTTP 200 response
- no JavaScript console errors
- no page-level horizontal scrolling at mobile width
  (document scrollWidth must not exceed the viewport width)

Usage:
    pip install playwright && playwright install chromium firefox
    python manage.py runserver 127.0.0.1:8000 &
    HMS_ADMIN_USER=... HMS_ADMIN_PASS=... HMS_STUDENT_USER=... HMS_STUDENT_PASS=... \
        python scripts/browser_sweep.py

Credentials are read from the environment; use demo/seed data only, never
real user accounts. Exits non-zero if any check fails.
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("HMS_BASE_URL", "http://127.0.0.1:8000")

ADMIN_PAGES = [
    "/dashboard/admin/",
    "/rooms/",
    "/rooms/applications/",
    "/rooms/allocations/",
    "/fees/manage/",
    "/complaints/manage/",
    "/students/",
    "/reports/",
]

STUDENT_PAGES = [
    "/dashboard/student/",
    "/rooms/apply/",
    "/fees/",
    "/complaints/",
    "/complaints/new/",
    "/profile/",
]

WIDTHS = {"desktop": 1280, "mobile": 390}


def login(page, username, password):
    page.goto(f"{BASE}/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button.login-button')
    page.wait_for_load_state("networkidle")


def check(page, path):
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    response = page.goto(f"{BASE}{path}")
    page.wait_for_load_state("networkidle")
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    inner_width = page.evaluate("window.innerWidth")
    return {
        "page": path,
        "status": response.status if response else None,
        "console_errors": console_errors,
        "horizontal_overflow": scroll_width > inner_width,
    }


def main():
    admin_user = os.environ["HMS_ADMIN_USER"]
    admin_pass = os.environ["HMS_ADMIN_PASS"]
    student_user = os.environ["HMS_STUDENT_USER"]
    student_pass = os.environ["HMS_STUDENT_PASS"]

    results = []
    with sync_playwright() as p:
        for browser_name, launcher in (("chromium", p.chromium), ("firefox", p.firefox)):
            browser = launcher.launch(headless=True)
            version = browser.version
            for width_name, width in WIDTHS.items():
                context = browser.new_context(viewport={"width": width, "height": 900})
                page = context.new_page()
                for role, user, password, pages in (
                    ("admin", admin_user, admin_pass, ADMIN_PAGES),
                    ("student", student_user, student_pass, STUDENT_PAGES),
                ):
                    login(page, user, password)
                    for path in pages:
                        result = check(page, path)
                        result.update({"browser": browser_name, "browser_version": version,
                                       "viewport": width_name, "role": role})
                        results.append(result)
                    page.context.clear_cookies()
                context.close()
            browser.close()

    failures = [r for r in results
                if r["status"] != 200 or r["console_errors"] or r["horizontal_overflow"]]
    print(json.dumps(results, indent=2))
    print(f"\n{len(results)} page checks, {len(failures)} failures")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
