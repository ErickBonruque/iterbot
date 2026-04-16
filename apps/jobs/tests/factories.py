import factory
from factory.django import DjangoModelFactory

from apps.jobs.models import Company, CompanyStatus, Job, JobApplication, JobStatus


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company

    cnpj = "11.222.333/0001-81"
    nome = factory.Sequence(lambda n: f"Empresa {n}")
    email = factory.Sequence(lambda n: f"contato{n}@empresa.com")
    telefone = "(41) 3333-4444"
    endereco = "Rua Teste, 123 - Curitiba/PR"
    descricao = "Empresa de tecnologia"
    contato_nome = "João Silva"
    contato_cargo = "Gerente de RH"
    status = CompanyStatus.APPROVED


class JobFactory(DjangoModelFactory):
    class Meta:
        model = Job

    company = factory.SubFactory(CompanyFactory)
    titulo = factory.Sequence(lambda n: f"Vaga de Estágio {n}")
    descricao = "Descrição da vaga de estágio"
    requisitos = "Cursando graduação"
    salario = "R$ 1.500,00"
    tipo = "Estágio"
    status = JobStatus.APPROVED


class JobApplicationFactory(DjangoModelFactory):
    class Meta:
        model = JobApplication

    user = factory.SubFactory("apps.users.tests.factories.UserProfileFactory")
    job = factory.SubFactory(JobFactory)
