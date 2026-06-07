"""Testes para endpoints admin WAHA — /admin/api/waha-status/ e /admin/api/waha-restart/.

WAHA-03: card de status em tempo real e botão de reconexão manual.
Stubs RED — implementação no Wave 2 (plano 54-03).
"""


class TestWahaStatusEndpoint:
    """GET /admin/api/waha-status/ deve retornar JSON com campos obrigatórios."""

    def test_returns_json_with_required_fields(self):
        """Resposta deve conter: status, session_status, response_time, last_check."""
        raise NotImplementedError(
            "Wave 2 (54-03): adicionar waha_status_api_view() em IterBotAdminSite "
            "e registrar em get_urls() como path('api/waha-status/', ...). "
            "Usar cache.get('bot_last_status') antes de BotHealthMonitor.check_bot_status(). "
            "JsonResponse com json_dumps_params={'default': str} para serializar datetime."
        )

    def test_anonymous_redirect(self):
        """Requisição anônima deve receber redirect 302 para login (self.admin_view() guard)."""
        raise NotImplementedError(
            "Wave 2 (54-03): self.admin_view() do UnfoldAdminSite garante staff_member_required. "
            "Anon deve receber redirect 302, não 200 ou 403."
        )


class TestWahaRestartEndpoint:
    """POST /admin/api/waha-restart/ deve chamar WahaClient.start_session() e retornar JSON."""

    def test_returns_success_true_or_false(self):
        """POST por staff retorna JsonResponse com chave 'success' (bool)."""
        raise NotImplementedError(
            "Wave 2 (54-03): adicionar waha_restart_api_view() em IterBotAdminSite. "
            "Verificar request.method == 'POST', chamar WahaClient().start_session(), "
            "retornar JsonResponse({'success': bool}). "
            "GET deve retornar JsonResponse({'error': 'Method not allowed'}, status=405)."
        )

    def test_post_requires_staff(self):
        """POST por usuário não-staff deve ser redirecionado (não 200)."""
        raise NotImplementedError(
            "Wave 2 (54-03): self.admin_view() rejeita não-staff. "
            "Usuário autenticado mas sem is_staff=True deve receber redirect, não 200."
        )
