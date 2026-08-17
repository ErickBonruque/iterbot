import structlog
from allauth.account.views import LoginView, LogoutView, SignupView
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View

from apps.companies.forms import CompanyOnlyForm, CompanyProfileForm, CompanySignupForm, JobForm
from apps.companies.mixins import ApprovedCompanyRequiredMixin
from apps.companies.services import CompaniesService
from apps.jobs.models import ApplicationStatus, Company, Job

logger = structlog.get_logger(__name__)


class CompanySignupView(SignupView):
    """View de registro de empresa.

    CompanySignupForm.save() cria User (allauth) + Company atomicamente.
    Após signup, allauth envia e-mail de verificação e redireciona para a
    página de 'verificação enviada'. Após confirmação pelo link do allauth,
    UTFPRAccountAdapter.get_email_confirmation_redirect_url() redireciona
    para /empresas/perfil/ quando o usuário possui Company vinculada.

    /empresas/criar/ é fallback para usuários que chegaram sem Company
    vinculada (ex: falha silenciosa em CompanySignupForm.save() durante signup).
    """

    template_name = "companies/signup.html"
    form_class = CompanySignupForm

    def dispatch(self, request, *args, **kwargs):
        # Rotas de empresa são independentes da sessão de aluno.
        # Se um aluno logado acessar /empresas/signup/, deslogamos antes de prosseguir
        # para que o allauth não redirecione por já estar autenticado.
        if request.user.is_authenticated:
            auth_logout(request)
        return super().dispatch(request, *args, **kwargs)


class CompanyLoginView(LoginView):
    """View de login de empresa."""

    template_name = "companies/login.html"

    def get_success_url(self):
        return "/empresas/perfil/"

    def dispatch(self, request, *args, **kwargs):
        # Mesma razão: deslogar sessão de aluno para não redirecionar erroneamente.
        if request.user.is_authenticated:
            auth_logout(request)
        return super().dispatch(request, *args, **kwargs)


class CompanyLogoutView(LogoutView):
    """View de logout de empresa."""

    next_page = "/empresas/login/"


class CompanyProfileView(LoginRequiredMixin, UpdateView):
    """View de edicao de perfil da empresa."""

    model = Company
    form_class = CompanyProfileForm
    template_name = "companies/profile.html"
    success_url = reverse_lazy("companies:profile")
    login_url = "/empresas/login/"

    def get_object(self, queryset=None):
        return CompaniesService.get_user_company_or_none(self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return redirect("/empresas/criar/")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return redirect("/empresas/criar/")
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["company"] = self.object
        # Vagas removidas nao aparecem para a empresa; filtrar aqui (e nao no
        # template) mantem o "nenhuma vaga cadastrada" correto quando todas
        # foram removidas.
        context["jobs"] = CompaniesService.list_company_jobs(self.object)
        return context

    def form_valid(self, form):
        messages.success(self.request, "Dados atualizados com sucesso.")
        return super().form_valid(form)


class CompanyCreateView(LoginRequiredMixin, View):
    """View de criacao de empresa para usuarios ja autenticados sem empresa."""

    login_url = "/empresas/login/"

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and CompaniesService.get_user_company_or_none(request.user) is not None
        ):
            return redirect("/empresas/perfil/")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = CompanyOnlyForm()
        return render(request, "companies/company_create.html", {"form": form})

    def post(self, request):
        form = CompanyOnlyForm(request.POST)
        if form.is_valid():
            CompaniesService.create_company_for_user(request.user, form.cleaned_data)
            messages.success(request, "Empresa cadastrada com sucesso. Aguardando aprovacao.")
            return redirect("/empresas/perfil/")
        return render(request, "companies/company_create.html", {"form": form})


class JobCreateView(ApprovedCompanyRequiredMixin, CreateView):
    """View de criacao de vaga."""

    model = Job
    form_class = JobForm
    template_name = "companies/job_form.html"
    success_url = reverse_lazy("companies:profile")
    login_url = "/empresas/login/"

    def form_valid(self, form):
        CompaniesService.prepare_job_for_creation(form.instance, self.request.user)
        messages.success(self.request, "Vaga cadastrada com sucesso. Aguardando aprovacao.")
        return super().form_valid(form)


class JobUpdateView(ApprovedCompanyRequiredMixin, UpdateView):
    """View de edicao de vaga."""

    model = Job
    form_class = JobForm
    template_name = "companies/job_form.html"
    success_url = reverse_lazy("companies:profile")
    login_url = "/empresas/login/"

    def get_object(self, queryset=None):
        job = super().get_object(queryset)
        return CompaniesService.get_editable_job_or_403(job, self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job"] = self.object
        return context

    def form_valid(self, form):
        messages.success(self.request, "Vaga atualizada com sucesso.")
        return super().form_valid(form)


class JobDeleteView(ApprovedCompanyRequiredMixin, View):
    """View de remocao de vaga (soft delete)."""

    template_name = "companies/job_confirm_delete.html"
    success_url = reverse_lazy("companies:profile")
    login_url = "/empresas/login/"

    def get_object(self, queryset=None):
        """Obter vaga excluindo ja removidas (retorna 404 natural)."""
        return CompaniesService.get_deletable_job_or_404(self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        """Exibe pagina de confirmacao."""
        job = CompaniesService.get_deletable_job_for_user_or_403(self.kwargs["pk"], request.user)
        return render(request, self.template_name, {"job": job})

    def post(self, request, *args, **kwargs):
        """Executa soft delete."""
        CompaniesService.soft_delete_job(self.kwargs["pk"], request.user)
        messages.success(request, "Vaga removida com sucesso.")
        return redirect(self.success_url)


class JobApplicationsListView(ApprovedCompanyRequiredMixin, ListView):
    """Lista as candidaturas recebidas pelas vagas da empresa."""

    template_name = "companies/applications.html"
    context_object_name = "applications"
    login_url = "/empresas/login/"
    paginate_by = 20

    def get_queryset(self):
        return CompaniesService.list_company_applications(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = ApplicationStatus.choices
        return context


class JobApplicationStatusUpdateView(ApprovedCompanyRequiredMixin, View):
    """Atualiza o status de uma candidatura (POST)."""

    login_url = "/empresas/login/"

    def post(self, request, *args, **kwargs):
        new_status = request.POST.get("status", "")
        CompaniesService.update_application_status(self.kwargs["pk"], request.user, new_status)
        messages.success(request, "Status da candidatura atualizado.")
        return redirect("companies:applications")
