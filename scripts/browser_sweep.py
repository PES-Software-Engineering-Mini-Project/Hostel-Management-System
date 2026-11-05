"""NFR-7 / SAD 4.5 browser sweep: every main page in Chromium and Firefox at 360 and 1280 px.

For each page it checks: HTTP 200, no console errors or uncaught page errors, and no
horizontal page scroll. It logs in as an admin and as a student who holds a room.

One-time install (not in requirements.txt, so CI and deployment stay small):

    pip install playwright
    playwright install chromium firefox
    # Linux only, if a browser fails to start: playwright install-deps

Run from the repository root (it starts its own `runserver` unless --base-url is given):

    python scripts/browser_sweep.py

It writes demo data into the configured database (db.sqlite3 by default) using the
`seed_demo` command plus two sweep accounts. Both steps are safe to re-run.
Exit code is 0 only when every check passes.
"""

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

PASSWORD = "sweep-password-123"  # demo data only
ADMIN_SRN = "PES1UG23SW001"
STUDENT_SRN = "PES1UG23SW002"
WIDTHS = (360, 1280)
IGNORED_CONSOLE = ("favicon.ico",)


def prepare_data():
    """seed_demo for volume, plus an admin and a student with a room, complaint and visitor."""
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db.models import F

    from complaints.models import Complaint
    from fees.models import FeeRecord
    from rooms.models import Room, RoomAllocation
    from visitors.models import Visitor

    call_command("seed_demo", verbosity=0)
    User = get_user_model()

    def account(srn, role, **extra):
        user, created = User.objects.get_or_create(
            srn=srn,
            defaults={
                "email": f"{srn.lower()}@example.com", "first_name": "Sweep",
                "last_name": role.title(), "contact_number": "9876543210", "role": role, **extra,
            },
        )
        user.set_password(PASSWORD)
        user.save()
        return user

    admin = account(ADMIN_SRN, User.Role.ADMIN)
    student = account(STUDENT_SRN, User.Role.STUDENT)

    if not RoomAllocation.objects.filter(student=student).exists():
        room = Room.objects.filter(occupied_count__lt=F("capacity")).order_by("pk").first()
        RoomAllocation.objects.create(student=student, room=room)
        Room.objects.filter(pk=room.pk).update(occupied_count=F("occupied_count") + 1)
    room = student.room_allocation.room

    if not Complaint.objects.filter(student=student).exists():
        # The room tag (FR-6.2, #49) may not be on this branch yet, so set it only if it exists.
        extra = {"room": room} if hasattr(Complaint, "room") else {}
        Complaint.objects.create(
            student=student, category="plumbing", description="Sweep complaint.", **extra
        )
    if not FeeRecord.objects.filter(student=student).exists():
        FeeRecord.objects.create(student=student, room=room, term="2026-27 Odd Semester", amount_due="20000.00")
    if not Visitor.objects.filter(host=student).exists():
        Visitor.objects.create(host=student, name="Sweep Visitor", phone="9123456780", purpose="Family visit")


def page_lists():
    """(label, path) lists per role. Visitor pages are included (FR-7)."""
    from django.urls import reverse

    from complaints.models import Complaint
    from reports.reports import REPORTS
    from rooms.models import RoomAllocation

    student = RoomAllocation.objects.get(student__srn=STUDENT_SRN).student
    complaint = Complaint.objects.filter(student=student).first()
    anonymous = [("login", reverse("login")), ("register", reverse("register"))]
    admin = [
        ("admin dashboard", reverse("admin-dashboard")),
        ("rooms", reverse("rooms:room-list")),
        ("add block", reverse("rooms:block-create")),
        ("add room", reverse("rooms:room-create")),
        ("pending applications", reverse("rooms:pending-applications")),
        ("allocations", reverse("rooms:allocation-list")),
        ("fees", reverse("fees:fee-list")),
        ("add fee", reverse("fees:fee-create")),
        ("complaints", reverse("complaints:complaint-list")),
        ("students", reverse("student-list")),
        ("student edit", reverse("student-edit", args=[student.pk])),
        ("reports", reverse("reports:index")),
        *[(f"report {slug}", reverse("reports:detail", args=[slug])) for slug in REPORTS],
        ("visitor log", "/visitors/manage/"),
    ]
    student_pages = [
        ("student dashboard", reverse("student-dashboard")),
        ("my fees", reverse("fees:my-fees")),
        ("my complaints", reverse("complaints:my-complaints")),
        ("raise complaint", reverse("complaints:raise")),
        ("complaint detail", reverse("complaints:detail", args=[complaint.pk])),
        ("my profile", reverse("profile-edit")),
        ("my visitors", "/visitors/"),
        ("register visitor", "/visitors/new/"),
    ]
    return anonymous, admin, student_pages


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(port):
    process = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/login/", timeout=1)
            return process
        except Exception:
            time.sleep(0.5)
    process.terminate()
    raise SystemExit("runserver did not start")


def check_page(page, base_url, path):
    """Return a list of problem strings for one page."""
    problems, errors = [], []

    def on_console(message):
        if message.type == "error" and not any(i in message.text for i in IGNORED_CONSOLE):
            errors.append(message.text)

    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append(str(e)))
    response = page.goto(base_url + path, wait_until="load")
    if response is None or response.status != 200:
        problems.append(f"HTTP {response.status if response else 'none'}")
    width = page.viewport_size["width"]
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    if scroll_width > width:
        wide = page.evaluate(
            """(w) => [...document.querySelectorAll('body *')]
                 .filter(e => e.getBoundingClientRect().right > w + 1)
                 .slice(0, 3).map(e => e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : ''))""",
            width,
        )
        problems.append(f"horizontal scroll ({scroll_width}px > {width}px; wide: {', '.join(wide)})")
    problems += [f"console error: {e[:120]}" for e in errors]
    return problems


def login(page, base_url, srn):
    page.goto(base_url + "/login/")
    page.fill("input[name=username]", srn)
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_load_state("load")
    if "/login/" in page.url:
        raise SystemExit(f"login failed for {srn}")


def sweep(playwright, base_url, browser_names, widths):
    anonymous, admin_pages, student_pages = page_lists()
    results = []  # (browser, width, role, label, path, problems)
    for name in browser_names:
        browser = getattr(playwright, name).launch()
        for width in widths:
            for role, srn, pages in (
                ("anonymous", None, anonymous), ("admin", ADMIN_SRN, admin_pages),
                ("student", STUDENT_SRN, student_pages),
            ):
                context = browser.new_context(viewport={"width": width, "height": 800})
                if srn:
                    login_page = context.new_page()
                    login(login_page, base_url, srn)
                    login_page.close()
                for label, path in pages:
                    # a fresh page per URL so console listeners do not pile up
                    probe = context.new_page()
                    probe.set_viewport_size({"width": width, "height": 800})
                    results.append((name, width, role, label, path, check_page(probe, base_url, path)))
                    probe.close()
                context.close()
        browser.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base-url", help="use a running server instead of starting one")
    parser.add_argument("--browsers", nargs="+", default=["chromium", "firefox"])
    parser.add_argument("--widths", nargs="+", type=int, default=list(WIDTHS))
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    prepare_data()
    server = None
    base_url = args.base_url
    if not base_url:
        port = free_port()
        server = start_server(port)
        base_url = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as playwright:
            results = sweep(playwright, base_url, args.browsers, args.widths)
    finally:
        if server:
            server.terminate()

    failures = [r for r in results if r[5]]
    print(f"{'browser':9} {'width':>5}  {'role':9} {'pages':>5} {'failed':>6}")
    for name in args.browsers:
        for width in args.widths:
            for role in ("anonymous", "admin", "student"):
                rows = [r for r in results if r[:3] == (name, width, role)]
                print(f"{name:9} {width:>5}  {role:9} {len(rows):>5} {sum(1 for r in rows if r[5]):>6}")
    for name, width, role, label, path, problems in failures:
        print(f"FAIL {name} {width}px {role} {label} {path}: {'; '.join(problems)}")
    print(f"\n{len(results)} checks, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
