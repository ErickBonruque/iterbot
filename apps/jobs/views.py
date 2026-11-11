"""Páginas públicas de vagas (sem login)."""

from django.views.generic import DetailView

from apps.jobs.models import Job
from apps.users.views import bot_whatsapp_url


class JobPublicDetailView(DetailView):
    """Página pública de uma vaga **publicada**: é o destino do link do resumo semanal.

    Qualquer outro status (pendente, recusada, removida, expirada, rascunho), vaga
    de empresa bloqueada ou id inexistente dá 404, sem vazar nenhum dado. Não
    mostra dados de contato nem pessoais da empresa: a candidatura é feita pelo
    WhatsApp, e a página só explica o caminho e leva ao chat do bot.
    """

    queryset = Job.objects.publicadas().select_related("company").prefetch_related("areas")
    template_name = "jobs/vaga_publica.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # None quando o WAHA não responde: a página mostra só a instrução.
        context["whatsapp_url"] = bot_whatsapp_url()
        return context
