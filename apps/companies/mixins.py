from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

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

        company = request.user.company
        if company.status != CompanyStatus.APPROVED:
            if company.status == CompanyStatus.BLOCKED:
                raise PermissionDenied(
                    "Sua empresa esta bloqueada. Entre em contato com a administracao."
                )
            raise PermissionDenied(
                "Sua empresa ainda nao foi aprovada. Aguarde a analise para publicar vagas."
            )
        return response
