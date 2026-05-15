"""Middleware that restricts /dashboard/ access to staff users only."""

from collections.abc import Callable
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

LOGIN_URL = "/accounts/login/"


class DashboardAuthMiddleware:
    """Redirect non-staff users away from /dashboard/ routes.

    Checks ``request.path_info.startswith('/dashboard/')`` and redirects
    to LOGIN_URL with ``next`` parameter if the user is not authenticated
    or not a staff member. Non-dashboard routes pass through untouched.

    Must be placed AFTER ``AuthenticationMiddleware`` in MIDDLEWARE so
    that ``request.user`` is available.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path_info

        if path.startswith("/dashboard/"):
            if not request.user.is_authenticated or not request.user.is_staff:
                login_url = f"{LOGIN_URL}?{urlencode({'next': path})}"
                return HttpResponseRedirect(login_url)

        return self.get_response(request)
