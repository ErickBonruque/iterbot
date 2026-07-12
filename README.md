# IterBot

Bot de WhatsApp para conectar estudantes da UTFPR com oportunidades de estágio e emprego — combina vagas online (agregadas via [python-jobspy](https://github.com/speedyapply/JobSpy)) com vagas locais cadastradas por empresas da região através de um portal web próprio.

> **Projeto de Iniciação Científica** — UTFPR Campus Santa Helena.
>
> ⚠️ **Sistema em desenvolvimento.** A plataforma ainda está em evolução ativa e não possui uma versão estável para uso geral. Funcionalidades, fluxos e configurações podem mudar sem aviso.

## Como funciona

- **Estudante:** interage exclusivamente pelo WhatsApp — autentica-se com o e-mail institucional (`@alunos.utfpr.edu.br`), escolhe áreas de interesse e recebe vagas locais e online direto no chat.
- **Empresa:** cadastra-se em um portal web, publica vagas por área e recebe candidaturas com mini-perfil do estudante. Vagas passam por validação administrativa antes de serem divulgadas.
- **Administração:** painel Django Admin customizado com métricas de negócio, observabilidade e status do bot.

## Stack

| Componente | Tecnologia |
|------------|------------|
| Backend | Django 5.2 + Django REST Framework (Python 3.11) |
| Banco de dados | PostgreSQL 15 |
| Cache / fila | Redis 7 + Celery |
| WhatsApp | [WAHA](https://waha.devlike.pro/) (WhatsApp HTTP API) |
| Busca de vagas | python-jobspy (LinkedIn, Indeed, Glassdoor) |
| Proxy / TLS | Traefik v3.6 + Let's Encrypt |
| E-mail | Multi-provider (Brevo, Resend, AWS SES, SMTP) com fallback |
| Execução | Docker Compose |

## Instalação

**Pré-requisitos:** Docker, Docker Compose e Git.

```bash
git clone https://github.com/ErickBonruque/iterbot.git
cd iterbot
```

## Início Rápido

1. **Configurar credenciais locais:**

   ```bash
   ./scripts/setup-local.sh
   ```

   O script copia `.env.example` para `.env` e gera senhas aleatórias para os serviços.

2. **Subir os serviços:**

   ```bash
   docker compose up -d
   ```

3. **Executar migrações, semear cursos e criar superusuário:**

   ```bash
   docker compose exec backend python manage.py migrate
   docker compose exec backend python manage.py seed_courses
   docker compose exec backend python manage.py createsuperuser
   ```

4. **Acessar os serviços:**

   | Serviço | URL |
   |---------|-----|
   | Django Admin | http://localhost:8000/admin/ |
   | Portal de empresas | http://localhost:8000/empresas/ |
   | WAHA Dashboard | http://localhost:3000/dashboard/ |

5. **Conectar o WhatsApp:** abra o WAHA Dashboard, inicie a sessão e escaneie o QR Code com o número que atenderá os estudantes.

Ver também [QUICKSTART.md](QUICKSTART.md) e [docs/getting-started/](docs/getting-started/).

## Comandos úteis

```bash
make dev-install      # Instalar dependências com Poetry
make start            # Subir todos os serviços
make stop             # Parar serviços
make health           # Verificar saúde dos serviços
make logs             # Ver logs (todos os serviços)
make logs-backend     # Ver logs do backend
make dev-test         # Rodar testes
make lint             # Verificar lint com ruff
make format           # Formatar código com ruff
make ci-check         # Lint + format check + typecheck
make backup           # Backup do banco e secrets
```

### Desenvolvimento local (sem Docker)

```bash
poetry install --all-extras
export DATABASE_URL="postgresql://iterbot_user:senha@localhost:5432/iterbot"
export REDIS_URL="redis://localhost:6379/0"
python manage.py migrate
python manage.py runserver
```

## Estrutura do Projeto

```
apps/
  bot/          # Bot WhatsApp: handlers, services, views, tasks, máquina de estados
  jobs/         # Vagas: models, tasks de coleta, validações, candidaturas
  companies/    # Portal de empresas (cadastro, vagas, candidaturas)
  users/        # Autenticação institucional e perfis
  courses/      # Cursos, áreas e termos de busca
  core/         # Base models, health checks, admin customizado, dashboards
infra/
  waha/         # Cliente HTTP para a API do WAHA
  jobspy/       # Serviço de busca de vagas online
  email/        # Factory multi-provider de e-mail (Brevo, Resend, SES, SMTP)
  security/     # Criptografia de campos sensíveis (EncryptedCharField)
  middleware/   # Correlation ID + logging estruturado
  traefik/      # Configuração do proxy reverso com TLS
config/         # Configuração por variáveis de ambiente + Docker Secrets
deployment/     # Scripts operacionais (backup, smoke check, rollback, secrets)
docs/           # Documentação (arquitetura, deploy, desenvolvimento)
```

## Documentação

- [Getting Started](docs/getting-started/) — configuração inicial
- [Arquitetura](docs/architecture/) — visão geral, fluxos do bot, regras de negócio e ADRs
- [Deploy](docs/deploy/) — guia de produção (VM institucional + Docker Compose)
- [Desenvolvimento](docs/development/) — guia de contribuição técnica
- [Configuração](docs/configuration/CONFIGURATION.md) — variáveis de ambiente
- [Troubleshooting](docs/troubleshooting/) — problemas comuns (WAHA, sessão do WhatsApp)

## Roadmap

O projeto segue em desenvolvimento. Entre os próximos passos:

- **Facilitar a personalização da plataforma** — permitir adaptar as diferentes partes do sistema para outras instituições ou contextos, incluindo nome, identidade visual, imagens, características, textos, configurações e demais elementos hoje específicos da UTFPR;
- Consolidar o deploy na infraestrutura institucional;
- Ampliar as fontes de vagas online e o resumo semanal por área;
- Melhorar a cobertura de testes e a observabilidade em produção.

## Contribuindo

Veja o guia em [CONTRIBUTING.md](CONTRIBUTING.md) — convenções de branches, commits (Conventional Commits via `cz commit`) e fluxo de PR.

## Licença

Projeto de Iniciação Científica da UTFPR Campus Santa Helena. Licença ainda não definida.
