import csv

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import admin_required

from .reports import REPORTS

# A cell starting with one of these is run as a formula by spreadsheet programs, so a
# student name such as "=HYPERLINK(...)" could do harm when an admin opens the file.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _get_report(slug):
    report = REPORTS.get(slug)
    if report is None:
        raise Http404("No such report.")
    return report


def csv_safe(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


@admin_required
def report_index(request):
    return render(request, "reports/index.html", {"reports": REPORTS.values()})


@admin_required
def report_detail(request, slug):
    report = _get_report(slug)
    data = report.build()
    return render(
        request,
        "reports/report_detail.html",
        {"report": report, "data": data, "reports": REPORTS.values()},
    )


@admin_required
def report_csv(request, slug):
    report = _get_report(slug)
    data = report.build()
    filename = f"hms-{report.slug}-report-{timezone.localdate():%Y-%m-%d}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    # The byte-order mark lets Excel read names with non-English letters correctly.
    response.write("﻿")
    writer = csv.writer(response)
    if data.is_empty:
        writer.writerow([report.empty_message])
        return response
    writer.writerow(data.headers)
    for row in data.rows:
        writer.writerow([csv_safe(value) for value in row])
    return response
