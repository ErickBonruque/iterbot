from django.db import models

from apps.core.models import TimeStampedModel


class BotMessage(TimeStampedModel):
    """
    Mensagens configuráveis do bot.
    """

    KEY_CHOICES = (
        ("welcome", "Boas-vindas / Menu"),
        ("login_prompt", "Solicitar Login"),
        ("login_prompt_ra", "Solicitar RA"),
        ("login_prompt_password", "Solicitar Senha"),
        ("login_prompt_email", "Solicitar Email"),
        ("login_success", "Login com Sucesso"),
        ("login_error", "Erro no Login"),
        ("logout_success", "Logout com Sucesso"),
        ("course_selection", "Seleção de Curso"),
        ("term_selection", "Seleção de Termo"),
        ("no_results", "Sem Resultados"),
        ("unknown_command", "Comando Desconhecido"),
        ("error_generic", "Erro Genérico"),
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
