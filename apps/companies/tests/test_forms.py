from django.contrib.auth.models import User
from django.test import TestCase

from apps.companies.forms import CompanyProfileForm, CompanySignupForm, JobForm
from apps.jobs.models import Company, CompanyStatus, Job


class TestCompanySignupForm(TestCase):
    """Testes do formulario de registro de empresa."""

    def setUp(self):
        self.valid_data = {
            'cnpj': '11.222.333/0001-81',
            'nome': 'Empresa Teste',
            'email': 'empresa@alunos.utfpr.edu.br',
            'telefone': '(41) 99999-0000',
            'contato_nome': 'Joao Silva',
            'contato_cargo': 'Gerente de RH',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
        }

    def test_valid_form(self):
        form = CompanySignupForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_cnpj(self):
        data = self.valid_data.copy()
        data['cnpj'] = '12.345.678/0001-00'
        form = CompanySignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('cnpj', form.errors)

    def test_duplicate_cnpj(self):
        user = User.objects.create_user(
            username='existing', email='existing@empresa.com', password='TestPass123!'
        )
        Company.objects.create(
            user=user,
            cnpj='11.222.333/0001-81',
            nome='Empresa Existente',
            email='existing@alunos.utfpr.edu.br',
            telefone='(41) 99999-0000',
            contato_nome='Maria',
            contato_cargo='Diretora',
            status=CompanyStatus.PENDING,
        )
        form = CompanySignupForm(data=self.valid_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cnpj', form.errors)

    def test_missing_required_fields(self):
        form = CompanySignupForm(data={})
        self.assertFalse(form.is_valid())
        for field in ['cnpj', 'nome', 'telefone', 'contato_nome', 'contato_cargo', 'email', 'password1', 'password2']:
            self.assertIn(field, form.errors, f"Campo {field} deveria ser obrigatorio")


class TestCompanyProfileForm(TestCase):
    """Testes do formulario de edicao de perfil."""

    def test_valid_form(self):
        data = {
            'nome': 'Empresa Atualizada',
            'telefone': '(41) 88888-0000',
            'endereco': 'Rua Nova, 456',
            'descricao': 'Nova descricao',
            'contato_nome': 'Pedro',
            'contato_cargo': 'Diretor',
        }
        form = CompanyProfileForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_excludes_cnpj(self):
        form = CompanyProfileForm()
        self.assertNotIn('cnpj', form.fields)
        self.assertNotIn('status', form.fields)
        self.assertNotIn('user', form.fields)
        self.assertNotIn('email', form.fields)


class TestJobForm(TestCase):
    """Testes do formulario de vaga."""

    def test_valid_form(self):
        data = {
            'titulo': 'Estagiario de TI',
            'descricao': 'Desenvolvimento web com Django',
            'requisitos': 'Cursando Ciencia da Computacao',
            'salario': 'R$ 1.200,00',
            'tipo': 'estagio',
        }
        form = JobForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_excludes_company_status(self):
        form = JobForm()
        self.assertNotIn('company', form.fields)
        self.assertNotIn('status', form.fields)
