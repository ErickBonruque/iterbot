from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

import structlog

from apps.users.services import UTFPRAuthService

logger = structlog.get_logger(__name__)


@login_required
def success_page(request):
    """
    Página simples de sucesso após login ou confirmação de e-mail.
    """
    return render(request, "account/success.html")


class ConfirmEmailView(View):
    """Handle email confirmation via token link."""

    def get(self, request, token):
        """Process email confirmation token.

        Args:
            request: HTTP request.
            token: UUID confirmation token from URL.

        Returns:
            HTTP response with confirmation result page.
        """
        auth_service = UTFPRAuthService()
        user = auth_service.confirm_email(token)

        if user:
            logger.info("email_confirmation_success", user_id=user.id, ra=user.ra)
            return render(request, "account/email_confirmed.html", {"success": True, "ra": user.ra})
        else:
            logger.warning("email_confirmation_failed", token=token[:8])
            return render(
                request,
                "account/email_confirmed.html",
                {"success": False, "error": "Link expirado ou inválido. Solicite um novo código no bot."},
            )
