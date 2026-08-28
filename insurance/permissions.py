"""Role helpers and view decorators.

Two roles exist:

* **Customer** - a ``User`` in the ``CUSTOMER`` group with a related ``Customer``.
* **Admin/staff** - a ``User`` with ``is_staff=True`` (superusers included).

The two sets are kept disjoint: a customer can never reach admin CRUD views,
and staff accounts are not treated as customers.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

CUSTOMER_GROUP = "CUSTOMER"


def is_customer(user):
    return (
        user.is_authenticated
        and not user.is_staff
        and user.groups.filter(name=CUSTOMER_GROUP).exists()
    )


def is_staff_user(user):
    return user.is_authenticated and user.is_staff


def customer_required(view_func):
    """Require an authenticated, non-staff customer account."""

    @wraps(view_func)
    @login_required(login_url="customerlogin")
    def _wrapped(request, *args, **kwargs):
        if not is_customer(request.user):
            raise PermissionDenied("This page is only available to customer accounts.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def staff_required(view_func):
    """Require an authenticated staff/admin account."""

    @wraps(view_func)
    @login_required(login_url="adminlogin")
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Administrator access is required for this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped
