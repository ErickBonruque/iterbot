from django.db import models

from apps.core.models import TimeStampedModel
from apps.courses.models import Course, SearchTerm
from apps.users.models import UserProfile


class ConversationState(TimeStampedModel):
    """Armazena o estado conversacional do bot, separado da identidade do usuário."""

    user = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="conversation_state",
        help_text="Perfil do usuário associado ao estado conversacional",
    )
    current_action = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Estado atual do fluxo conversacional do bot",
    )
    selected_course = models.ForeignKey(
        Course,
        related_name="conversation_selections",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    selected_term = models.ForeignKey(
        SearchTerm,
        related_name="conversation_selections",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    flow_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dados temporários do fluxo conversacional",
    )

    class Meta:
        verbose_name = "Estado de Conversa"
        verbose_name_plural = "Estados de Conversa"

    def __str__(self):
        return f"ConversationState({self.user_id}: {self.current_action or 'idle'})"
