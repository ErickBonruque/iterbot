# IterBot

**English** · [Português](README.md)

[![CI](https://github.com/ErickBonruque/iterbot/actions/workflows/ci.yml/badge.svg)](https://github.com/ErickBonruque/iterbot/actions/workflows/ci.yml)

A WhatsApp bot that connects UTFPR students with internships and jobs. It combines online job posts
(collected with [python-jobspy](https://github.com/speedyapply/JobSpy)) with local job posts that
companies of the region publish on the project's own web portal.

> **Undergraduate research project** at UTFPR (Federal University of Technology – Paraná), Santa
> Helena campus. The software is registered with INPI (Brazilian National Institute of Industrial
> Property).
>
> **Status:** in active development. There is no stable release yet. Features and settings can change.

## How it works

- **Student:** uses only WhatsApp. The student signs in with the university email
  (`@alunos.utfpr.edu.br`), selects areas of interest and gets local and online jobs in the chat.
- **Company:** registers on a web portal, publishes jobs by area and receives applications with a
  short student profile. An administrator approves each job before the bot sends it to students.
- **Administration:** a custom Django Admin panel with business metrics, observability and bot status.

## Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.2 + Django REST Framework (Python 3.11) |
| Database | PostgreSQL 15 |
| Cache / queue | Redis 7 + Celery |
| WhatsApp | [WAHA](https://waha.devlike.pro/) (WhatsApp HTTP API) |
| Job search | python-jobspy (LinkedIn, Indeed, Glassdoor) + Adzuna API |
| Proxy / TLS | Traefik v3.6 + Let's Encrypt |
| Email | Several providers (Brevo, Resend, AWS SES, SMTP) with fallback |
| Runtime | Docker Compose |

## Installation

**Requirements:** Docker, Docker Compose and Git.

```bash
git clone https://github.com/ErickBonruque/iterbot.git
cd iterbot
```

## Quick start

1. **Create the local credentials:**

   ```bash
   ./scripts/setup-local.sh
   ```

   The script copies `.env.example` to `.env` and generates random passwords for the services.

2. **Start the services:**

   ```bash
   docker compose up -d
   ```

3. **Run the migrations, load the courses and create a superuser:**

   ```bash
   docker compose exec backend python manage.py migrate
   docker compose exec backend python manage.py seed_courses
   docker compose exec backend python manage.py createsuperuser
   ```

4. **Open the services:**

   | Service | URL |
   |---------|-----|
   | Django Admin | http://localhost:8000/admin/ |
   | Company portal | http://localhost:8000/empresas/ |
   | WAHA Dashboard | http://localhost:3000/dashboard/ |

5. **Connect WhatsApp:** open the WAHA Dashboard, start a session and scan the QR code with the phone
   number that will answer the students.

See also [QUICKSTART.md](QUICKSTART.md) and [docs/getting-started/](docs/getting-started/)
(in Portuguese).

## Useful commands

```bash
make dev-install      # Install the dependencies with Poetry
make start            # Start all services
make stop             # Stop the services
make health           # Check the health of the services
make logs             # Show the logs (all services)
make logs-backend     # Show the backend logs
make dev-test         # Run the tests
make lint             # Lint with ruff
make format           # Format with ruff
make ci-check         # Lint + format check + type check
make backup           # Back up the database and the secrets
```

### Local development (without Docker)

```bash
poetry install --all-extras
export DATABASE_URL="postgresql://iterbot_user:password@localhost:5432/iterbot"
export REDIS_URL="redis://localhost:6379/0"
python manage.py migrate
python manage.py runserver
```

## Project structure

```
apps/
  bot/          # WhatsApp bot: handlers, services, views, tasks, state machine
  jobs/         # Jobs: models, collection tasks, validation, applications
  companies/    # Company portal (registration, jobs, applications)
  users/        # University sign-in and profiles
  courses/      # Courses, areas and search terms
  core/         # Base models, health checks, custom admin, dashboards
infra/
  waha/         # HTTP client for the WAHA API
  adzuna/       # Adzuna API client (online jobs)
  jobspy/       # Online job search service
  email/        # Email provider factory (Brevo, Resend, SES, SMTP)
  security/     # Encryption of sensitive fields (EncryptedCharField)
  middleware/   # Correlation ID + structured logging
  traefik/      # Reverse proxy configuration with TLS
config/         # Configuration from environment variables + Docker Secrets
deployment/     # Operation scripts (backup, smoke check, rollback, secrets)
docs/           # Documentation (architecture, deploy, development)
```

## Documentation (in Portuguese)

- [Getting Started](docs/getting-started/): first setup
- [Architecture](docs/architecture/): overview, bot flows, business rules and ADRs
- [Deploy](docs/deploy/): production guide (university VM + Docker Compose)
- [Development](docs/development/): technical contribution guide
- [Configuration](docs/configuration/CONFIGURATION.md): environment variables
- [Troubleshooting](docs/troubleshooting/): common problems (WAHA, WhatsApp session)

## Roadmap

The project is still in development. Next steps include:

- **Make the platform easy to customize:** let other institutions or contexts change name, visual
  identity, images, features, texts, settings and the other parts that are specific to UTFPR today.
- Complete the deploy on the university infrastructure.
- Add more online job sources and the weekly summary by area.
- Improve the test coverage and the observability in production.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) (in Portuguese): branch rules, commits (Conventional Commits
with `cz commit`) and the PR flow.

## License

Undergraduate research project of UTFPR, Santa Helena campus. The license is not defined yet.
