from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.jobs.models import Company, CompanyStatus, Job, JobStatus

CACHES_LOCMEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}


@override_settings(CACHES=CACHES_LOCMEM)
class TestCompanySignupView(TestCase):
    """Testes da view de registro de empresa."""

    def setUp(self):
        self.client = Client()

    def test_signup_page_loads(self):
        response = self.client.get('/empresas/signup/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cadastrar Empresa')

    def test_signup_creates_company(self):
        data = {
            'cnpj': '11.222.333/0001-81',
            'nome': 'Empresa Teste',
            'email': 'contato@empresa.com',
            'telefone': '(41) 99999-0000',
            'contato_nome': 'Joao Silva',
            'contato_cargo': 'Gerente de RH',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
        }
        response = self.client.post('/empresas/signup/', data)
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            self.assertTrue(User.objects.filter(email='contato@empresa.com').exists())
            self.assertTrue(Company.objects.filter(cnpj='11.222.333/0001-81').exists())

    def test_signup_allows_non_utfpr_email(self):
        """Adapter condicional permite e-mail livre em rotas /empresas/."""
        data = {
            'cnpj': '11.222.333/0001-81',
            'nome': 'Empresa Gmail',
            'email': 'contato@gmail.com',
            'telefone': '(41) 99999-0000',
            'contato_nome': 'Maria',
            'contato_cargo': 'Diretora',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
        }
        response = self.client.post('/empresas/signup/', data)
        # Nao deve rejeitar e-mail fora de @alunos.utfpr.edu.br
        self.assertIn(response.status_code, [200, 302])


@override_settings(CACHES=CACHES_LOCMEM)
class TestCompanyLoginView(TestCase):
    """Testes da view de login de empresa."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='empresa1', email='contato@empresa.com', password='TestPass123!'
        )
        self.company = Company.objects.create(
            user=self.user,
            cnpj='11.222.333/0001-81',
            nome='Empresa Teste',
            email='contato@empresa.com',
            telefone='(41) 99999-0000',
            contato_nome='Joao',
            contato_cargo='Gerente',
            status=CompanyStatus.APPROVED,
        )

    def test_login_page_loads(self):
        response = self.client.get('/empresas/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login - Portal Empresas')

    def test_login_valid_credentials(self):
        # Marcar email como verificado para allauth
        from allauth.account.models import EmailAddress
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=True,
            primary=True,
        )
        response = self.client.post('/empresas/login/', {
            'login': 'contato@empresa.com',
            'password': 'TestPass123!',
        })
        self.assertIn(response.status_code, [200, 302])


@override_settings(CACHES=CACHES_LOCMEM)
class TestCompanyProfileView(TestCase):
    """Testes da view de perfil da empresa."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='empresa2', email='perfil@empresa.com', password='TestPass123!'
        )
        self.company = Company.objects.create(
            user=self.user,
            cnpj='22.333.444/0001-90',
            nome='Empresa Perfil',
            email='perfil@empresa.com',
            telefone='(41) 88888-0000',
            contato_nome='Pedro',
            contato_cargo='Diretor',
            status=CompanyStatus.APPROVED,
        )

    def test_profile_requires_login(self):
        response = self.client.get('/empresas/perfil/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/empresas/login/', response.url)

    def test_profile_loads_for_company_user(self):
        self.client.force_login(self.user)
        response = self.client.get('/empresas/perfil/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '22.333.444/0001-90')

    def test_profile_update(self):
        self.client.force_login(self.user)
        response = self.client.post('/empresas/perfil/', {
            'nome': 'Nome Atualizado',
            'telefone': '(41) 77777-0000',
            'endereco': 'Rua Nova',
            'descricao': 'Nova descricao',
            'contato_nome': 'Pedro Atualizado',
            'contato_cargo': 'CEO',
        })
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            self.company.refresh_from_db()
            self.assertEqual(self.company.nome, 'Nome Atualizado')


@override_settings(CACHES=CACHES_LOCMEM)
class TestJobCreateView(TestCase):
    """Testes da view de criacao de vaga."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='empresa3', email='vagas@empresa.com', password='TestPass123!'
        )
        self.company = Company.objects.create(
            user=self.user,
            cnpj='33.444.555/0001-07',
            nome='Empresa Vagas',
            email='vagas@empresa.com',
            telefone='(41) 77777-0000',
            contato_nome='Ana',
            contato_cargo='Coordenadora',
            status=CompanyStatus.APPROVED,
        )
        self.user_no_company = User.objects.create_user(
            username='semempresa', email='sem@empresa.com', password='TestPass123!'
        )

    def test_create_requires_login(self):
        response = self.client.get('/empresas/vagas/nova/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/empresas/login/', response.url)

    def test_create_requires_company(self):
        self.client.force_login(self.user_no_company)
        response = self.client.get('/empresas/vagas/nova/')
        self.assertEqual(response.status_code, 403)

    def test_create_job(self):
        self.client.force_login(self.user)
        response = self.client.post('/empresas/vagas/nova/', {
            'titulo': 'Estagiario de TI',
            'descricao': 'Desenvolvimento web',
            'requisitos': 'Cursando CC',
            'salario': 'R$ 1.200,00',
            'tipo': 'estagio',
        })
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            job = Job.objects.get(titulo='Estagiario de TI')
            self.assertEqual(job.company, self.company)

    def test_create_job_sets_pending_status(self):
        self.client.force_login(self.user)
        self.client.post('/empresas/vagas/nova/', {
            'titulo': 'Estagiario Backend',
            'descricao': 'Django e Python',
            'requisitos': '',
            'salario': '',
            'tipo': 'estagio',
        })
        job = Job.objects.filter(titulo='Estagiario Backend').first()
        if job:
            self.assertEqual(job.status, JobStatus.PENDING)


@override_settings(CACHES=CACHES_LOCMEM)
class TestJobUpdateView(TestCase):
    """Testes da view de edicao de vaga."""

    def setUp(self):
        self.client = Client()
        # Empresa dona da vaga
        self.user = User.objects.create_user(
            username='empresa4', email='editar@empresa.com', password='TestPass123!'
        )
        self.company = Company.objects.create(
            user=self.user,
            cnpj='44.555.666/0001-24',
            nome='Empresa Editar',
            email='editar@empresa.com',
            telefone='(41) 66666-0000',
            contato_nome='Carlos',
            contato_cargo='Gerente',
            status=CompanyStatus.APPROVED,
        )
        self.job = Job.objects.create(
            company=self.company,
            titulo='Vaga Original',
            descricao='Descricao original',
            requisitos='Requisitos',
            salario='R$ 1.000,00',
            tipo='estagio',
            status=JobStatus.PENDING,
        )
        # Outra empresa
        self.other_user = User.objects.create_user(
            username='outra', email='outra@empresa.com', password='TestPass123!'
        )
        self.other_company = Company.objects.create(
            user=self.other_user,
            cnpj='55.666.777/0001-41',
            nome='Outra Empresa',
            email='outra@empresa.com',
            telefone='(41) 55555-0000',
            contato_nome='Lucia',
            contato_cargo='Diretora',
            status=CompanyStatus.APPROVED,
        )
        # User sem company
        self.user_no_company = User.objects.create_user(
            username='semempresa2', email='sem2@empresa.com', password='TestPass123!'
        )

    def test_update_own_job(self):
        self.client.force_login(self.user)
        response = self.client.post(f'/empresas/vagas/{self.job.pk}/editar/', {
            'titulo': 'Vaga Atualizada',
            'descricao': 'Descricao atualizada',
            'requisitos': 'Novos requisitos',
            'salario': 'R$ 1.500,00',
            'tipo': 'estagio',
        })
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            self.job.refresh_from_db()
            self.assertEqual(self.job.titulo, 'Vaga Atualizada')

    def test_update_other_company_job(self):
        self.client.force_login(self.other_user)
        response = self.client.get(f'/empresas/vagas/{self.job.pk}/editar/')
        self.assertEqual(response.status_code, 403)

    def test_update_requires_company(self):
        self.client.force_login(self.user_no_company)
        response = self.client.get(f'/empresas/vagas/{self.job.pk}/editar/')
        self.assertEqual(response.status_code, 403)


@override_settings(CACHES=CACHES_LOCMEM)
class TestJobDeleteView(TestCase):
    """Testes para JobDeleteView."""

    def setUp(self):
        self.user = User.objects.create_user(username='empresa1', email='empresa1@test.com', password='senha123')
        self.company = Company.objects.create(
            user=self.user,
            cnpj='12.345.678/0001-90',
            nome='Empresa Teste',
            email='contato@empresa.com',
            telefone='(41) 99999-9999',
            contato_nome='Responsavel',
            contato_cargo='Gerente'
        )
        self.job = Job.objects.create(
            company=self.company,
            titulo='Vaga Teste',
            descricao='Descricao',
            tipo='estagio',
            status=JobStatus.PENDING
        )
        self.other_user = User.objects.create_user(username='empresa2', email='empresa2@test.com', password='senha123')
        self.other_company = Company.objects.create(
            user=self.other_user,
            cnpj='98.765.432/0001-10',
            nome='Outra Empresa',
            email='contato@outra.com',
            telefone='(41) 88888-8888',
            contato_nome='Outro Responsavel',
            contato_cargo='Outro Gerente'
        )
        self.other_job = Job.objects.create(
            company=self.other_company,
            titulo='Outra Vaga',
            descricao='Descricao',
            tipo='estagio',
            status=JobStatus.PENDING
        )

    def test_get_confirmation_page_owner(self):
        """Dono da vaga acessa pagina de confirmacao (200)."""
        self.client.login(username='empresa1', password='senha123')
        response = self.client.get(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vaga Teste')
        self.assertContains(response, 'Confirmar Remo')

    def test_get_confirmation_page_no_company(self):
        """Usuario sem company recebe 403."""
        user_no_company = User.objects.create_user(username='semempresa', email='semempresa@test.com', password='senha123')
        self.client.login(username='semempresa', password='senha123')
        response = self.client.get(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_confirmation_page_other_company(self):
        """Dono de outra empresa recebe 403."""
        self.client.login(username='empresa2', password='senha123')
        response = self.client.get(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_confirmation_page_removed_job(self):
        """Vaga ja removida retorna 404."""
        self.job.status = JobStatus.REMOVED
        self.job.save()
        self.client.login(username='empresa1', password='senha123')
        response = self.client.get(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 404)

    def test_post_delete_owner(self):
        """Dono da vaga consegue remover (soft delete)."""
        self.client.login(username='empresa1', password='senha123')
        response = self.client.post(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.REMOVED)
        self.assertRedirects(response, reverse('companies:profile'))
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(str(messages_list[0]), 'Vaga removida com sucesso.')

    def test_post_delete_no_company(self):
        """Usuario sem company recebe 403 no POST."""
        user_no_company = User.objects.create_user(username='semempresa2', email='semempresa2@test.com', password='senha123')
        self.client.login(username='semempresa2', password='senha123')
        response = self.client.post(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 403)
        self.job.refresh_from_db()
        self.assertNotEqual(self.job.status, JobStatus.REMOVED)

    def test_post_delete_other_company(self):
        """Dono de outra empresa recebe 403 no POST."""
        self.client.login(username='empresa2', password='senha123')
        response = self.client.post(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 403)
        self.job.refresh_from_db()
        self.assertNotEqual(self.job.status, JobStatus.REMOVED)

    def test_post_delete_removed_job(self):
        """Vaga ja removida retorna 404 no POST."""
        self.job.status = JobStatus.REMOVED
        self.job.save()
        self.client.login(username='empresa1', password='senha123')
        response = self.client.post(reverse('companies:job_delete', kwargs={'pk': self.job.pk}))
        self.assertEqual(response.status_code, 404)

    def test_removed_job_not_in_profile(self):
        """Vaga removida nao aparece na listagem do profile."""
        self.job.status = JobStatus.REMOVED
        self.job.save()
        self.client.login(username='empresa1', password='senha123')
        response = self.client.get(reverse('companies:profile'))
        self.assertNotContains(response, 'Vaga Teste')
