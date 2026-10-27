"""Role-based access decorators shared by HMS feature apps."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import User


def role_required(role):
    """Require authentication and a stored HMS role, returning 403 for other roles."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied("You do not have permission to access this area.")
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


student_required = role_required(User.Role.STUDENT)
admin_required = role_required(User.Role.ADMIN)
