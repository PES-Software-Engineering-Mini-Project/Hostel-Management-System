"""Pagination shared by every HMS list page (NFR-5).

Each list shows ``HMS_PAGE_SIZE`` rows at a time so pages stay fast with about 1000
students and 500 rooms. A missing, non-numeric or out-of-range ``?page=`` falls back to
the first or last page instead of raising an error.
"""

from django.conf import settings
from django.core.paginator import Paginator


def paginate(request, queryset, per_page=None):
    paginator = Paginator(queryset, per_page or settings.HMS_PAGE_SIZE)
    return paginator.get_page(request.GET.get("page"))
