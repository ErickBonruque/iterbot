import structlog
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from allauth.account.views import LoginView, LogoutView, SignupView

from apps.companies.forms import CompanyProfileForm, CompanySignupForm, JobForm
from apps.companies.mixins import CompanyRequiredMixin
from apps.jobs.models import Company, Job, JobStatus

logger = structlog.get_logger(__name__)


class CompanySignupView(SignupView):
    """View de registro de empresa."""
    template_name = 'companies/signup.html'
    form_class = CompanySignupForm
    success_url = '/empresas/perfil/'


class CompanyLoginView(LoginView):
    """View de login de empresa."""
    template_name = 'companies/login.html'
    success_url = '/empresas/perfil/'


class CompanyLogoutView(LogoutView):
    """View de logout de empresa."""
    next_page = '/empresas/login/'


class CompanyProfileView(LoginRequiredMixin, UpdateView):
    """View de edicao de perfil da empresa."""
    model = Company
    form_class = CompanyProfileForm
    template_name = 'companies/profile.html'
    success_url = reverse_lazy('companies:profile')
    login_url = '/empresas/login/'

    def get_object(self, queryset=None):
        return self.request.user.company

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.get_object()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Dados atualizados com sucesso.')
        return super().form_valid(form)


class JobCreateView(CompanyRequiredMixin, CreateView):
    """View de criacao de vaga."""
    model = Job
    form_class = JobForm
    template_name = 'companies/job_form.html'
    success_url = reverse_lazy('companies:profile')
    login_url = '/empresas/login/'

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        form.instance.status = JobStatus.PENDING
        messages.success(self.request, 'Vaga cadastrada com sucesso. Aguardando aprovacao.')
        return super().form_valid(form)


class JobUpdateView(CompanyRequiredMixin, UpdateView):
    """View de edicao de vaga."""
    model = Job
    form_class = JobForm
    template_name = 'companies/job_form.html'
    success_url = reverse_lazy('companies:profile')
    login_url = '/empresas/login/'

    def get_object(self, queryset=None):
        job = super().get_object(queryset)
        try:
            user_company = self.request.user.company
        except Exception:
            raise PermissionDenied("Voce nao tem permissao para editar esta vaga.")
        if job.company != user_company:
            raise PermissionDenied("Voce nao tem permissao para editar esta vaga.")
        return job

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job'] = self.object
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Vaga atualizada com sucesso.')
        return super().form_valid(form)
