from allauth.account.forms import SignupForm
from django import forms
from django.core.exceptions import ValidationError

from apps.companies.services import CompaniesService
from apps.jobs.models import Company, Job
from apps.jobs.validators import validate_cnpj


class CompanySignupForm(SignupForm):
    """
    Formulario de registro de empresa.
    Estende o SignupForm do allauth com campos adicionais da empresa.
    """

    cnpj = forms.CharField(
        max_length=18,
        label="CNPJ",
        validators=[validate_cnpj],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "XX.XXX.XXX/XXXX-XX",
            }
        ),
    )
    nome = forms.CharField(
        max_length=255,
        label="Nome da Empresa",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Razao social ou nome fantasia",
            }
        ),
    )
    telefone = forms.CharField(
        max_length=20,
        label="Telefone",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "(XX) XXXXX-XXXX",
            }
        ),
    )
    contato_nome = forms.CharField(
        max_length=255,
        label="Nome do Responsavel",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome completo do responsavel",
            }
        ),
    )
    contato_cargo = forms.CharField(
        max_length=100,
        label="Cargo do Responsavel",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ex: Gerente de RH",
            }
        ),
    )

    def clean_cnpj(self):
        """Verifica unicidade do CNPJ."""
        value = self.cleaned_data.get("cnpj")
        if Company.objects.filter(cnpj=value).exists():
            raise ValidationError(
                "Ja existe uma empresa cadastrada com este CNPJ.",
                code="duplicate_cnpj",
            )
        return value

    def save(self, request):
        """Cria User (via allauth) e Company vinculada via service único."""
        user = super().save(request)
        CompaniesService.create_company_for_user(user, self.cleaned_data)
        # Armazena o e-mail em sessao para exibir na tela de verificacao
        # (allauth.EmailVerificationSentView nao adiciona o email no contexto
        # por padrao, entao guardamos aqui para o template ler).
        request.session["pending_verification_email"] = user.email
        return user


class CompanyOnlyForm(forms.Form):
    """
    Formulario de criacao de empresa para usuarios ja autenticados.
    Nao cria novo usuario — apenas cadastra a empresa vinculada ao usuario logado.
    """

    cnpj = forms.CharField(
        max_length=18,
        label="CNPJ",
        validators=[validate_cnpj],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "XX.XXX.XXX/XXXX-XX",
            }
        ),
    )
    nome = forms.CharField(
        max_length=255,
        label="Nome da Empresa",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Razao social ou nome fantasia",
            }
        ),
    )
    telefone = forms.CharField(
        max_length=20,
        label="Telefone",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "(XX) XXXXX-XXXX",
            }
        ),
    )
    contato_nome = forms.CharField(
        max_length=255,
        label="Nome do Responsavel",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome completo do responsavel",
            }
        ),
    )
    contato_cargo = forms.CharField(
        max_length=100,
        label="Cargo do Responsavel",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ex: Gerente de RH",
            }
        ),
    )

    def clean_cnpj(self):
        value = self.cleaned_data.get("cnpj")
        if Company.objects.filter(cnpj=value).exists():
            raise ValidationError(
                "Ja existe uma empresa cadastrada com este CNPJ.",
                code="duplicate_cnpj",
            )
        return value


class CompanyProfileForm(forms.ModelForm):
    """
    Formulario de edicao de perfil da empresa.
    Exclui campos sensiveis (CNPJ, status, user, email).
    """

    class Meta:
        model = Company
        fields = ["nome", "telefone", "endereco", "descricao", "contato_nome", "contato_cargo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "telefone": forms.TextInput(attrs={"class": "form-control"}),
            "endereco": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "contato_nome": forms.TextInput(attrs={"class": "form-control"}),
            "contato_cargo": forms.TextInput(attrs={"class": "form-control"}),
        }


class JobForm(forms.ModelForm):
    """
    Formulario de criacao/edicao de vaga.
    Exclui campos company e status (atribuidos via view).
    """

    TIPO_CHOICES = [
        ("estagio", "Estagio"),
        ("clt", "CLT"),
        ("pj", "PJ"),
        ("temporario", "Temporario"),
    ]

    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        label="Tipo da Vaga",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Job
        fields = ["titulo", "descricao", "requisitos", "salario", "tipo"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: Estagiario de Desenvolvimento Web",
                }
            ),
            "descricao": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Descreva as atividades e responsabilidades da vaga",
                }
            ),
            "requisitos": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Conhecimentos e habilidades necessarias",
                }
            ),
            "salario": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: R$ 1.200,00 ou A combinar",
                }
            ),
        }
