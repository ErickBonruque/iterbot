from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.jobs.models import CompanyStatus


class CompanyRequiredMixin(LoginRequiredMixin):
    """
    Mixin que exige que o usuario esteja autenticado e tenha uma Company vinculada.

    Não diferencia status (PENDING/APPROVED/BLOCKED) — usar
    ``ApprovedCompanyRequiredMixin`` em endpoints que exigem aprovação ativa.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, "status_code") and response.status_code == 302:
            return response
        try:
            _ = request.user.company
        except Exception as err:
            raise PermissionDenied("Usuario nao possui empresa vinculada.") from err
        return response


class ApprovedCompanyRequiredMixin(CompanyRequiredMixin):
    """
    Exige que a Company vinculada esteja com status APPROVED.

    Bloqueia operações sensíveis (criação/edição/remoção de vagas) para empresas
    PENDING (aguardando análise) ou BLOCKED (suspensas pelo admin). Sem esse
    gate, qualquer empresa recém-cadastrada poderia publicar vagas mesmo antes
    da curadoria manual prevista no fluxo da milestone v1.0.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, "status_code") and response.status_code == 302:
            return response

        # super() (CompanyRequiredMixin) já garantiu que user.company existe.
        # Guard explícito para proteger contra refatorações futuras que removam o check.
        try:
            company = request.user.company
        except Exception as err:
            raise PermissionDenied("Usuario nao possui empresa vinculada.") from err
        if company.status != CompanyStatus.APPROVED:
            if company.status == CompanyStatus.BLOCKED:
                messages.error(
                    request,
                    "Sua empresa está bloqueada. Entre em contato com a administração.",
                )
            else:
                messages.warning(
                    request,
                    "Sua empresa ainda não foi aprovada. Aguarde a análise para publicar vagas.",
                )
            return redirect("/empresas/perfil/")
        return response
