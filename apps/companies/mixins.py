from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class CompanyRequiredMixin(LoginRequiredMixin):
    """
    Mixin que exige que o usuario esteja autenticado e tenha uma Company vinculada.
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
