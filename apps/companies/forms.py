from allauth.account.forms import SignupForm
from django import forms
from django.core.exceptions import ValidationError

from apps.companies.services import CompaniesService
from apps.courses.models import Area
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
        label="Nome da empresa",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Razão social ou nome fantasia",
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
        label="Nome do responsável",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome completo do responsável",
            }
        ),
    )
    contato_cargo = forms.CharField(
        max_length=100,
        label="Cargo do responsável",
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
                "Já existe uma empresa cadastrada com este CNPJ.",
                code="duplicate_cnpj",
            )
        return value

    def save(self, request):
        """Cria User (via allauth) e Company vinculada via service único."""
        user = super().save(request)
        CompaniesService.create_company_for_user(user, self.cleaned_data)
        # Armazena o e-mail em sessão para exibir na tela de verificação
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
        label="Nome da empresa",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Razão social ou nome fantasia",
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
        label="Nome do responsável",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome completo do responsável",
            }
        ),
    )
    contato_cargo = forms.CharField(
        max_length=100,
        label="Cargo do responsável",
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
                "Já existe uma empresa cadastrada com este CNPJ.",
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
        labels = {
            "nome": "Nome da empresa",
            "telefone": "Telefone",
            "endereco": "Endereço",
            "descricao": "Descrição",
            "contato_nome": "Nome do responsável",
            "contato_cargo": "Cargo do responsável",
        }
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

    # O valor gravado é o próprio rótulo: painel, bot e admin mostram o mesmo texto.
    TIPO_CHOICES = [
        ("Estágio", "Estágio"),
        ("CLT", "CLT"),
        ("PJ", "PJ"),
        ("Temporário", "Temporário"),
    ]

    tipo = forms.ChoiceField(
        choices=[("", "Selecione o tipo"), *TIPO_CHOICES],
        label="Tipo da vaga",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    areas = forms.ModelMultipleChoiceField(
        queryset=Area.objects.filter(is_active=True),
        required=False,
        label="Áreas de interesse",
        help_text="Marque as áreas para as quais a vaga é direcionada. "
        "Se não marcar nenhuma, a vaga será ofertada para todas as áreas.",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Job
        fields = ["titulo", "descricao", "requisitos", "salario", "tipo", "areas"]
        labels = {
            "titulo": "Título da vaga",
            "descricao": "Descrição",
            "requisitos": "Requisitos",
            "salario": "Salário",
        }
        widgets = {
            "titulo": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: Estagiário de Desenvolvimento Web",
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
                    "placeholder": "Conhecimentos e habilidades necessárias",
                }
            ),
            "salario": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex: R$ 1.200,00 ou A combinar",
                }
            ),
        }

    def has_changed(self):
        """Como o padrão, mas ignora diferença só de quebra de linha.

        O navegador envia ``\\r\\n`` nas áreas de texto. Sem isso, salvar sem mexer
        em nada uma vaga gravada com ``\\n`` contaria como edição e a mandaria de
        volta para análise.
        """
        return any(not self._so_quebra_de_linha(nome) for nome in self.changed_data)

    def _so_quebra_de_linha(self, nome):
        inicial = self.get_initial_for_field(self.fields[nome], nome)
        enviado = self.data.get(self.add_prefix(nome))
        if not (isinstance(inicial, str) and isinstance(enviado, str)):
            return False
        return inicial.replace("\r\n", "\n") == enviado.replace("\r\n", "\n")
