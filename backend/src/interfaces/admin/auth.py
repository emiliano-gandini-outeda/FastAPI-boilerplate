"""Authentication backend for SQLAdmin."""

import hmac

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from ...infrastructure.config.settings import get_settings


class AdminAuth(AuthenticationBackend):
    """Session-based authentication for the admin interface."""

    async def login(self, request: Request) -> bool:
        """Validate login credentials and create session."""
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        settings = get_settings()

        if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
            return False

        username = str(username or "")
        password = str(password or "")

        if hmac.compare_digest(username, settings.ADMIN_USERNAME) and hmac.compare_digest(
            password, settings.ADMIN_PASSWORD
        ):
            request.session.update({"admin_authenticated": True})
            return True

        return False

    async def logout(self, request: Request) -> bool:
        """Clear the admin session."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Check if the current request is authenticated."""
        return bool(request.session.get("admin_authenticated", False))
