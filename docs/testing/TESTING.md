<!-- generated-by: gsd-doc-writer -->

# Testes — IterBot UTFPR

Este documento descreve a estrutura de testes, como executá-los e como escrever novos testes no projeto IterBot.

## Framework e Configuração

O projeto utiliza **pytest** como framework de testes, com as seguintes extensões:

| Pacote | Versão | Função |
|--------|--------|--------|
| `pytest` | ^7.4.3 | Framework principal |
| `pytest-django` | ^4.7.0 | Integração com Django (banco de teste, fixtures) |
| `pytest-mock` | ^3.12.0 | Helper para `unittest.mock` via fixture `mocker` |
| `pytest-cov` | ^4.1.0 | Relatórios de cobertura |
| `factory-boy` | ^3.3.0 | Fábricas de objetos para testes |
| `faker` | ^20.1.0 | Geração de dados falsos |
| `responses` | ^0.24.1 | Mock de requisições HTTP |

### Configuração do pytest

A configuração está em `pyproject.toml` na seção `[tool.pytest.ini_options]`:

```toml
DJANGO_SETTINGS_MODULE = "waha_bot.settings"
python_files = ["test_*.py", "*_test.py"]
addopts = "-v --tb=short --strict-markers --cov=waha_bot --cov-report=term-missing --cov-report=html --cov-report=xml --cov-report=lcov"
testpaths = ["apps"]
```

- `DJANGO_SETTINGS_MODULE` aponta para `waha_bot.settings`.
- Os testes são descobertos no diretório `apps/`.
- Arquivos de teste seguem os padrões `test_*.py` ou `*_test.py`.

### Configuração de cobertura

Em `[tool.coverage.run]` e `[tool.coverage.report]`:

```toml
[tool.coverage.run]
source = ["apps", "config", "infra", "waha_bot"]
branch = true
omit = ["*/migrations/*", "*/tests/*", "*/__pycache__/*", "*/conftest.py"]

[tool.coverage.report]
fail_under = 70
show_missing = true
skip_covered = false
show_contexts = true
```

- **Cobertura mínima exigida:** 70% (`fail_under = 70`).
- Cobertura de branch está habilitada (`branch = true`).
- Migrations, arquivos de teste e `__pycache__` são excluídos da medição.

## Executando os Testes

### Comandos disponíveis

| Comando | Descrição |
|---------|-----------|
| `make dev-test` | Executa testes dentro do container Docker (backend) |
| `make test` | Executa testes dentro do container Docker (backend) |
| `make ci-check` | Executa lint (ruff) + verificação de formatação + mypy |
| `poetry run pytest` | Executa testes localmente com cobertura |
| `poetry run pytest --cov -v` | Executa testes com cobertura verbosa |

### Executando um subconjunto de testes

```bash
# Apenas um app
poetry run pytest apps/bot/

# Apenas um arquivo
poetry run pytest apps/bot/tests/test_bot_service.py

# Apenas uma classe
poetry run pytest apps/bot/tests/test_bot_service.py::BotServiceMenuTests

# Apenas um teste
poetry run pytest apps/bot/tests/test_bot_service.py::BotServiceMenuTests::test_new_user_receives_menu_prompt

# Por palavra-chave
poetry run pytest -k "waha"
```

### Ambiente de teste

Os testes locais usam `DJANGO_SETTINGS_MODULE=waha_bot.settings` (definido no `pyproject.toml`). Para que os testes funcionem localmente, é necessário ter as variáveis de ambiente configuradas ou usar o container Docker.

Na CI, os serviços necessários são provisionados via GitHub Actions:

- **PostgreSQL 15** — banco `iterbot_test`, usuário `iterbot_user`
- **Redis 7** — broker/cache

Variáveis de ambiente da CI:

```yaml
DATABASE_URL: postgresql://iterbot_user:test_password@localhost:5432/iterbot_test
REDIS_URL: redis://localhost:6379/0
```

## Escrevendo Novos Testes

### Convenções de nomenclatura

- **Diretório:** `apps/<app>/tests/`
- **Arquivo:** `test_<modulo>.py` (ex.: `test_bot_service.py`, `test_models.py`)
- **Classe:** `PascalCase` com sufixo descritivo (ex.: `BotServiceMenuTests`, `TestCompanySignupView`)
- **Método:** `test_<descricao>` em snake_case (ex.: `test_login_flow_with_option_one`)

### Duas abordagens de teste

O projeto utiliza duas abordagens para testes unitários:

#### 1. `django.test.TestCase` (com banco de dados)

Para testes que precisam de banco de dados (models, views, integração):

```python
from django.test import TestCase

class MinhaClasseDeTeste(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create(
            phone_number="5511999999999@c.us",
            is_authenticated_utfpr=True,
        )

    def test_comportamento_esperado(self):
        # usa banco de dados de teste
        self.assertEqual(self.user.current_action, None)
```

#### 2. `pytest` com `@pytest.mark.django_db` (sem TestCase)

Para testes mais leves, usando fixtures do pytest e factory-boy:

```python
import pytest
from apps.jobs.tests.factories import CompanyFactory, JobFactory

@pytest.mark.django_db
class TestCompany:
    def test_company_creation(self):
        company = CompanyFactory()
        assert company.pk is not None
```

### Fábricas (factory-boy)

O projeto usa `factory-boy` com `DjangoModelFactory` para criar dados de teste. As fábricas ficam em `apps/<app>/tests/factories.py`:

- `apps/jobs/tests/factories.py` — `CompanyFactory`, `JobFactory`, `JobApplicationFactory`
- `apps/users/tests/factories.py` — `UserProfileFactory`

Para criar uma nova fábrica:

```python
import factory
from factory.django import DjangoModelFactory
from apps.meuapp.models import MeuModel

class MeuModelFactory(DjangoModelFactory):
    class Meta:
        model = MeuModel

    campo = factory.Sequence(lambda n: f"valor_{n}")
```

### Testando com mocks

Para dependências externas (WAHA API, email, etc.), use `unittest.mock`:

```python
from unittest.mock import MagicMock, patch

class MeuTeste(TestCase):
    def test_algo_com_mock(self):
        cliente_mock = MagicMock()
        cliente_mock.send_message.return_value = True

        with patch("apps.bot.tasks.BotHealthMonitor") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.check_bot_status.return_value = {"status": "online"}
            mock_cls.return_value = mock_instance
            # ... teste
```

### Settings de teste

O arquivo `apps/users/tests/test_settings.py` define configurações de teste que sobrescrevem o settings de produção:

```python
from waha_bot.settings import *

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
```

Alguns testes usam `@override_settings` para alterar configurações pontuais:

```python
from django.test import override_settings

@override_settings(CACHES=CACHES_LOCMEM)
class TestCompanySignupView(TestCase):
    ...
```

### Testes de API (DRF)

Para testes de API REST, use `APIClient` do DRF:

```python
from rest_framework.test import APIClient

class MinhaAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_endpoint(self):
        response = self.client.get("/api/bot/configuration/active/")
        self.assertEqual(response.status_code, 200)
```

## Requisitos de Cobertura

- **Mínimo exigido:** 70% (`fail_under = 70` no `pyproject.toml`)
- O pipeline de CI falha se a cobertura ficar abaixo deste limiar
- Relatórios gerados: terminal (`term-missing`), HTML (`htmlcov/`), XML (`coverage.xml`), LCOV (`coverage.lcov`)
- Linhas excluídas da cobertura: `pragma: no cover`, `raise NotImplementedError`, `if TYPE_CHECKING:`, `def __repr__`, `@abstractmethod`, bloco `__main__`

## Integração com CI

### Workflow de CI (`.github/workflows/ci.yml`)

Acionado em **pull requests** e **pushes em branches `feature/*` e `fix/*`**.

Jobs:

| Job | O que faz |
|-----|-----------|
| **Lint** | `ruff check .` + `ruff format --check .` |
| **Test** | `pytest --cov -v` com PostgreSQL e Redis como serviços |
| **Security** | `pip-audit` (vulnerabilidades críticas) + `Trivy` (FS scan, severidades CRITICAL/HIGH/MEDIUM/LOW) |

O job **Test** gera artefatos de cobertura:
- Upload do HTML (`coverage-html`) e XML (`coverage-xml`) como artefatos com retenção de 7 dias
- Upload para Codecov (não bloqueia a CI se falhar)
- Comentário de cobertura em PRs via `romeovs/lcov-reporter-action`

### Workflow de Deploy (`.github/workflows/deploy.yml`)

Acionado em **push para `master`** ou **workflow_dispatch manual**.

O job **CI Gate** executa obrigatoriamente antes do deploy:
- Lint (`ruff check .`)
- Formatação (`ruff format --check .`)
- Testes (`pytest --cov -v`)

Somente após a aprovação do CI Gate, os jobs de `deploy` ou `rollback` podem executar.

### Pre-commit hooks

O projeto usa **pre-commit** com os seguintes hooks (`.pre-commit-config.yaml`):

| Hook | Função |
|------|--------|
| `trailing-whitespace` | Remove espaços em branco no final de linhas |
| `end-of-file-fixer` | Garante newline no final dos arquivos |
| `check-added-large-files` | Previne commit de arquivos grandes |
| `check-merge-conflict` | Detecta marcadores de conflito |
| `check-yaml/json/toml` | Valida sintaxe de arquivos de configuração |
| `ruff` | Lint com auto-fix |
| `ruff-format` | Formatação automática |
| `commitizen` | Valida mensagens de commit (conventional commits) |

Instalação dos hooks:

```bash
make pre-commit-install
```

## Estrutura dos Testes por App

```
apps/
  bot/tests/
    __init__.py
    test_bot_service.py     # BotService: menu, login, fluxos do bot
    test_bot_configuration.py  # BotConfiguration model e BotService init
    test_waha_client.py     # WahaClient: send_message, start_session, structlog
    test_tasks.py            # Celery tasks: health check, reconexão, alertas
    test_health.py           # BotHealthMonitor: check_bot_status, logging structlog
    test_webhook_security.py # Segurança do webhook: SSL redirect, isenção de rota
  companies/tests/
    __init__.py
    test_views.py            # Views: signup, login, perfil, CRUD de vagas
    test_forms.py            # Formulários: CompanySignup, CompanyProfile, Job
  dashboard/tests/
    test_bot_configuration_api.py  # API DRF: configuração ativa, sincronização admin
  jobs/tests/
    __init__.py
    factories.py             # CompanyFactory, JobFactory, JobApplicationFactory
    test_models.py           # Models: Company, Job, JobApplication
    test_tasks.py            # Tasks: formatação de review, deduplicação, URLs
  users/tests/
    __init__.py
    factories.py             # UserProfileFactory
    test_auth_flow.py        # Fluxo de autenticação: signup, login, logout, reset
    test_settings.py         # Settings de teste (cache locmem, email backend)
```