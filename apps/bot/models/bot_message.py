from django.db import models

from apps.core.models import TimeStampedModel


class BotMessage(TimeStampedModel):
    """Mensagens configuráveis do bot."""

    KEY_CHOICES = (
        ("welcome", "Boas-vindas / Menu (legado)"),
        ("login_prompt", "Solicitar Login (legado)"),
        ("login_prompt_ra", "Solicitar RA (legado)"),
        ("login_prompt_password", "Solicitar Senha (legado)"),
        ("login_prompt_email", "Solicitar Email (legado)"),
        ("login_success", "Login com Sucesso (legado)"),
        ("login_error", "Erro no Login (legado)"),
        ("logout_success", "Logout com Sucesso (legado)"),
        ("course_selection", "Seleção de Curso (legado)"),
        ("term_selection", "Seleção de Termo (legado)"),
        ("no_results", "Sem Resultados (legado)"),
        ("unknown_command", "Comando Desconhecido (legado)"),
        ("error_generic", "Erro Genérico (legado)"),
        ("auth.login_already_registered", "Auth: já cadastrado"),
        ("auth.login_prompt_ra", "Auth: solicitar RA"),
        ("auth.login_ra_too_short", "Auth: RA curto"),
        ("auth.login_prompt_password", "Auth: solicitar senha"),
        ("auth.login_validating_credentials", "Auth: validando credenciais"),
        ("auth.login_prompt_email", "Auth: solicitar e-mail"),
        ("auth.login_error", "Auth: erro de login"),
        ("auth.login_flow_error", "Auth: erro de fluxo"),
        ("auth.login_email_too_short", "Auth: e-mail curto"),
        ("auth.login_email_invalid", "Auth: e-mail inválido"),
        ("auth.login_waiting_confirmation", "Auth: aguardando confirmação"),
        ("auth.login_resend_success", "Auth: reenvio sucesso"),
        ("auth.login_resend_error", "Auth: reenvio erro"),
        ("auth.login_waiting_status", "Auth: status confirmação"),
        ("auth.logout_success", "Auth: logout sucesso"),
        ("menu.main_authenticated", "Menu: principal autenticado"),
        ("menu.main_unauthenticated", "Menu: principal não autenticado"),
        ("menu.company_onboarding_menu", "Menu: onboarding empresas"),
        ("menu.company_onboarding_signup", "Menu: cadastro empresa"),
        ("menu.company_onboarding_publish", "Menu: publicar vaga"),
        ("menu.unknown_command", "Menu: comando desconhecido"),
        ("search.auth_required", "Busca: autenticação necessária"),
        ("search.no_courses", "Busca: sem cursos"),
        ("search.selection_intro", "Busca: seleção de curso"),
        ("search.invalid_course_non_numeric", "Busca: curso não numérico"),
        ("search.invalid_course_number", "Busca: curso inválido"),
        ("search.missing_course", "Busca: curso ausente"),
        ("search.no_terms_for_course", "Busca: curso sem termos"),
        ("search.term_selection_intro", "Busca: seleção de termo"),
        ("search.invalid_term_non_numeric", "Busca: termo não numérico"),
        ("search.invalid_term_number", "Busca: termo inválido"),
        ("search.searching_jobs", "Busca: buscando vagas"),
        ("search.no_jobs", "Busca: sem vagas"),
        ("search.results_header", "Busca: cabeçalho de resultados"),
        ("review.missing_course", "Review: curso ausente"),
        ("review.searching_review", "Review: buscando review"),
        ("review.review_error", "Review: erro ao buscar"),
        ("review.no_jobs", "Review: sem vagas"),
        ("review.weekly_header", "Review: cabeçalho semanal"),
        ("review.weekly_summary", "Review: resumo semanal"),
        ("review.weekly_footer", "Review: rodapé semanal"),
        ("system.action_cancelled", "Sistema: ação cancelada"),
        ("system.portal_unavailable", "Sistema: portal indisponível"),
        ("system.webhook_error", "Sistema: erro webhook"),
        ("system.method_not_allowed", "Sistema: método não permitido"),
        ("tasks.alert_subject_offline", "Tasks: assunto alerta offline"),
        ("tasks.alert_offline_intro", "Tasks: introdução alerta"),
        ("tasks.alert_status_line", "Tasks: linha de status"),
        ("tasks.alert_error_line", "Tasks: linha de erro"),
        ("tasks.alert_reconnect_line", "Tasks: linha de reconexão"),
        ("tasks.confirm_email_subject", "Tasks: assunto confirmação"),
        ("tasks.confirm_email_greeting", "Tasks: saudação confirmação"),
    )

    key = models.CharField(
        max_length=50,
        choices=KEY_CHOICES,
        unique=True,
        help_text="Chave identificadora da mensagem",
    )
    text = models.TextField(
        help_text="Conteúdo da mensagem. Use {variaveis} para interpolação se necessário."
    )
    description = models.CharField(
        max_length=255, blank=True, help_text="Descrição do uso desta mensagem"
    )

    class Meta:
        verbose_name = "Mensagem do Bot"
        verbose_name_plural = "Mensagens do Bot"
        ordering = ["key"]

    def __str__(self):
        return f"{self.get_key_display()}"
