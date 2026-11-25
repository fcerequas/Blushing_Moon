from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Intercepts every HTTP request from an authenticated member whose
    `must_change_password` flag is True and redirects them to the
    onboarding password-change view.
    """

    def __init__(self, get_response):
        # One-time configuration and initialization when the web server starts.
        # `get_response` is the next middleware in the chain (or the final view).
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 1. Check if the user is logged in and flagged for a password reset
        if (
            request.user.is_authenticated
            and getattr(request.user, "must_change_password", False)
        ):
            password_change_url = reverse("force_password_change")
            logout_url = reverse("logout")

            # 2. Whitelist allowed paths to prevent an infinite redirect loop
            allowed_paths = {password_change_url, logout_url}

            if (
                request.path not in allowed_paths
                and not request.path.startswith("/static/")
                and not request.path.startswith("/media/")
            ):
                return redirect(password_change_url)

        # 3. Otherwise, let the request continue normally to the view
        response = self.get_response(request)
        return response