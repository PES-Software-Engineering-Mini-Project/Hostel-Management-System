"""Report definitions shared by the HTML pages and the CSV downloads (SRS §3.1, §3.3).

Each report builds its header and rows once, so the page and the CSV always show the same
figures. Every report runs a fixed number of queries however many rooms, students or
complaints there are.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from complaints.models import Complaint
from fees.models import FeeRecord
from rooms.models import Room

PERCENTAGE_QUANTUM = Decimal("0.1")
MONEY_QUANTUM = Decimal("0.01")


@dataclass
class ReportData:
    headers: list
    rows: list
    totals: list = field(default_factory=list)  # shown under the HTML table only

    @property
    def is_empty(self):
        return not self.rows


@dataclass(frozen=True)
class Report:
    slug: str
    title: str
    summary: str
    empty_message: str
    build: Callable[[], ReportData]
    numeric_columns: frozenset = frozenset()


def _money(value):
    # SQLite returns sums such as Decimal("10000"); fix two places so CSVs read the same
    # on every database.
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _percentage(part, whole):
    if not whole:
        return Decimal("0.0")
    return (Decimal(part) * 100 / Decimal(whole)).quantize(
        PERCENTAGE_QUANTUM, rounding=ROUND_HALF_UP
    )


def occupancy_report():
    """Rooms and beds per block and floor."""
    groups = (
        Room.objects.values("block__name", "floor")
        .annotate(
            rooms=Count("id"),
            beds=Sum("capacity"),
            occupied=Sum("occupied_count"),
        )
        .order_by("block__name", "floor")
    )
    rows = []
    total_rooms = total_beds = total_occupied = 0
    for group in groups:
        free = group["beds"] - group["occupied"]
        rows.append(
            [
                group["block__name"],
                group["floor"],
                group["rooms"],
                group["beds"],
                group["occupied"],
                free,
                _percentage(group["occupied"], group["beds"]),
            ]
        )
        total_rooms += group["rooms"]
        total_beds += group["beds"]
        total_occupied += group["occupied"]
    totals = []
    if rows:
        totals = [
            "All blocks",
            "",
            total_rooms,
            total_beds,
            total_occupied,
            total_beds - total_occupied,
            _percentage(total_occupied, total_beds),
        ]
    return ReportData(
        headers=["Block", "Floor", "Rooms", "Beds", "Occupied beds", "Free beds", "Occupancy (%)"],
        rows=rows,
        totals=totals,
    )


def fee_due_report():
    """Every fee record with money still owed, one row per student per term."""
    records = (
        FeeRecord.objects.with_totals()
        .annotate(
            outstanding=ExpressionWrapper(
                F("amount_due") - F("total_paid"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .filter(outstanding__gt=0)
        .select_related("student", "room__block")
        .order_by("student__srn", "term")
    )
    rows = []
    total_outstanding = Decimal("0.00")
    for record in records:
        room = f"{record.room.block.name} {record.room.room_number}" if record.room else ""
        rows.append(
            [
                record.student.srn,
                record.student.get_full_name(),
                room,
                record.term,
                _money(record.amount_due),
                _money(record.total_paid),
                _money(record.outstanding),
            ]
        )
        total_outstanding += _money(record.outstanding)
    totals = []
    if rows:
        students = len({row[0] for row in rows})
        label = "1 student" if students == 1 else f"{students} students"
        totals = [label, "", "", "", "", "", total_outstanding]
    return ReportData(
        headers=["SRN", "Student", "Room", "Term", "Amount due", "Paid", "Balance"],
        rows=rows,
        totals=totals,
    )


def complaint_report():
    """Complaint counts by category and status."""
    counts = {
        (row["category"], row["status"]): row["n"]
        for row in Complaint.objects.values("category", "status").annotate(n=Count("id"))
    }
    if not counts:
        return ReportData(headers=[], rows=[])
    statuses = Complaint.Status.choices
    rows = []
    for category, category_label in Complaint.Category.choices:
        per_status = [counts.get((category, status), 0) for status, _ in statuses]
        rows.append([category_label, *per_status, sum(per_status)])
    status_totals = [sum(row[i + 1] for row in rows) for i in range(len(statuses))]
    return ReportData(
        headers=["Category", *(label for _, label in statuses), "Total"],
        rows=rows,
        totals=["All categories", *status_totals, sum(status_totals)],
    )


REPORTS = {
    report.slug: report
    for report in [
        Report(
            slug="occupancy",
            title="Occupancy report",
            summary="Rooms, beds and occupancy for each block and floor.",
            empty_message="No rooms have been set up yet, so there is no occupancy to report.",
            build=occupancy_report,
            numeric_columns=frozenset({1, 2, 3, 4, 5, 6}),
        ),
        Report(
            slug="fee-dues",
            title="Fee-due report",
            summary="Students who still owe fees, with the balance for each term.",
            empty_message="No student has an outstanding fee balance.",
            build=fee_due_report,
            numeric_columns=frozenset({4, 5, 6}),
        ),
        Report(
            slug="complaints",
            title="Complaint report",
            summary="How many complaints are open, in progress and resolved in each category.",
            empty_message="No complaints have been raised yet.",
            build=complaint_report,
            numeric_columns=frozenset({1, 2, 3, 4}),
        ),
    ]
}
