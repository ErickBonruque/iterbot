import structlog
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views import View

from apps.companies.company_auth_service import CompanyAuthService
from apps.companies.services import CompaniesService
from apps.users.services import UTFPRAuthService

logger = structlog.get_logger(__name__)


def success_page(request):
    """Página de sucesso após login ou confirmação de e-mail.

    Acessível por usuários anônimos (redirecionados pós-confirmação)
    e por usuários autenticados (login normal).
    """
    context = {
        "is_authenticated": request.user.is_authenticated,
    }
    if request.user.is_authenticated:
        context["user_email"] = request.user.email
        # Check if user has a company to show contextual link
        company = CompaniesService.get_user_company_or_none(request.user)
        context["has_company"] = company is not None
    return render(request, "account/success.html", context)


class ConfirmEmailView(View):
    """Handle email confirmation via token link.

    After successful confirmation, auto-logs in the user and redirects
    to the success page (students) or company profile (companies).
    """

    def get(self, request, token):
        """Process email confirmation token.

        Args:
            request: HTTP request.
            token: UUID confirmation token from URL.

        Returns:
            Redirect on success, error page on failure.
        """
        auth_service = UTFPRAuthService()
        profile = auth_service.confirm_email(token)

        if profile:
            logger.info("email_confirmation_success", user_id=profile.id, ra=profile.ra)
            # Get or create Django User for auto-login.
            # For bot users (WhatsApp): profile.user may be None — create a User
            # and link it to the existing UserProfile.
            # For web users (allauth): profile.user already exists.
            user = profile.user
            if user is None:
                from django.contrib.auth.models import User

                # Check if User with this email already exists
                # (e.g. created via allauth web signup)
                user = User.objects.filter(email=profile.email).first()
                if user is not None:
                    # Link existing User to this profile
                    profile.user = user
                    profile.save(update_fields=["user"])
                else:
                    # Create new User. Temporarily disconnect the post_save
                    # signal that auto-creates a UserProfile, since our profile
                    # already exists and would conflict on the unique email field.
                    from django.db.models.signals import post_save

                    from apps.users.signals import create_user_profile

                    post_save.disconnect(create_user_profile, sender=User)
                    try:
                        user = User.objects.create_user(
                            username=profile.email,
                            email=profile.email,
                            password=None,
                        )
                    finally:
                        post_save.connect(create_user_profile, sender=User)

                    # Link our existing profile to the newly created User
                    profile.user = user
                    profile.save(update_fields=["user"])

            # Log the user in using Django's session auth
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Notifica o aluno proativamente via WhatsApp (reseta estado e envia mensagem).
            from apps.bot.tasks import notify_student_confirmed_whatsapp

            notify_student_confirmed_whatsapp.delay(profile.id)

            # Redirect based on user type
            company = CompaniesService.get_user_company_or_none(user)
            if company:
                return redirect("/empresas/perfil/")
            return redirect("/accounts/success/")
        else:
            logger.warning("email_confirmation_failed", token=token[:8])
            return render(
                request,
                "account/email_confirmed.html",
                {
                    "success": False,
                    "error": "Link expirado ou inválido. Solicite um novo código no bot.",
                },
            )


class ConfirmCompanyEmailView(View):
    """Confirma o vínculo entre número WhatsApp e conta de empresa via token."""

    def get(self, request, token):
        service = CompanyAuthService()
        profile = service.confirm_company_email(token)

        if profile:
            logger.info(
                "company_email_confirmation_success",
                user_id=profile.id,
                company_id=profile.company_id,
            )
            from apps.bot.tasks import notify_company_confirmed_whatsapp

            notify_company_confirmed_whatsapp.delay(profile.id)
            return render(
                request,
                "account/email_confirmed.html",
                {
                    "success": True,
                    "message": (
                        "Conta empresa vinculada com sucesso! "
                        "Você receberá uma mensagem no WhatsApp em instantes."
                    ),
                },
            )

        logger.warning("company_email_confirmation_failed", token=token[:8])
        return render(
            request,
            "account/email_confirmed.html",
            {
                "success": False,
                "error": "Link expirado ou inválido. Solicite um novo link pelo WhatsApp.",
            },
        )
