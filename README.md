# CapyVagas-UTFPR

> **Assistente de WhatsApp para estudantes da UTFPR**  
> Projeto de Iniciação Científica - Campus Santa Helena

Bot de WhatsApp integrado ao WAHA com dashboard administrativo em Django/DRF. Arquitetura refatorada para produção com foco em segurança, escalabilidade e observabilidade.

## 🌟 Características

- ✅ **Seguro**: Criptografia de dados sensíveis, HTTPS com Let's Encrypt, Docker Secrets
- ✅ **Escalável**: PostgreSQL, Redis, cache distribuído
- ✅ **Observável**: Logs estruturados JSON, correlation IDs, health checks
- ✅ **Robusto**: Health checks, restart policies, connection pooling
- ✅ **Manutenível**: SOLID principles, type hints, handlers especializados
- ✅ **Testável**: Framework de testes, cobertura de código

## 📁 Arquitetura

```
CapyVagas-UTFPR/
├── apps/                    # Aplicações Django por domínio
│   ├── bot/                 # Lógica do bot e handlers
│   │   └── handlers/        # Handlers especializados (SRP)
│   ├── courses/             # Gerenciamento de cursos
│   ├── users/               # Perfis de usuários
│   ├── jobs/                # Buscas e logs de vagas
│   ├── dashboard/           # Interface administrativa
│   └── core/                # Funcionalidades compartilhadas
├── config/                  # Configurações e variáveis de ambiente
├── infra/                   # Infraestrutura e integrações
│   ├── jobspy/              # Integração JobSpy
│   ├── waha/                # Cliente WAHA
│   ├── middleware/          # Middlewares customizados
│   ├── security/            # Criptografia e segurança
│   └── traefik/             # Configuração Traefik
├── docker/                  # Dockerfiles
├── secrets/                 # Docker secrets (não commitados)
├── waha_bot/                # Configuração Django
└── pyproject.toml           # Poetry e ferramentas
```

### Componentes

- **Backend Django**: API REST e lógica de negócio
- **PostgreSQL**: Banco de dados relacional
- **Redis**: Cache e sessões distribuídas
- **WAHA**: WhatsApp HTTP API
- **Traefik**: Reverse proxy com HTTPS automático

## 🚀 Início Rápido

### Pré-requisitos

- Docker e Docker Compose
- Python 3.11+ (para desenvolvimento local)
- Poetry (para gerenciamento de dependências)

### Instalação com Docker (Recomendado)

1. **Clone o repositório:**
```bash
git clone https://github.com/ErickBonruque/CapyVagas-UTFPR.git
cd CapyVagas-UTFPR
```

2. **Configure as variáveis de ambiente:**
```bash
cp .env.example .env
# Edite .env com suas configurações
```

3. **Configure os secrets:**
```bash
cd secrets

# Copie os exemplos
cp django_secret_key.txt.example django_secret_key.txt
cp postgres_password.txt.example postgres_password.txt
cp waha_api_key.txt.example waha_api_key.txt
cp waha_dashboard_password.txt.example waha_dashboard_password.txt
cp waha_swagger_password.txt.example waha_swagger_password.txt

# Gere valores seguros
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > django_secret_key.txt
openssl rand -base64 32 > postgres_password.txt
openssl rand -base64 32 > waha_api_key.txt
openssl rand -base64 32 > waha_dashboard_password.txt
openssl rand -base64 32 > waha_swagger_password.txt

cd ..
```

4. **Inicie os serviços:**
```bash
docker-compose up -d
```

5. **Execute as migrações:**
```bash
docker-compose exec backend python manage.py migrate
```

6. **Crie um superusuário:**
```bash
docker-compose exec backend python manage.py createsuperuser
```

7. **Acesse a aplicação:**
- Dashboard: `http://localhost/dashboard/`
- Admin Django: `http://localhost/admin/`
- WAHA Dashboard: `http://waha.localhost/`
- Traefik Dashboard: `http://localhost:8080/`
- Health Check: `http://localhost/health/`

### Desenvolvimento Local

1. **Instale o Poetry:**
```bash
pip install poetry
```

2. **Instale as dependências:**
```bash
poetry install
```

3. **Ative o ambiente virtual:**
```bash
poetry shell
```

4. **Configure o banco de dados local:**
```bash
# Use SQLite para desenvolvimento
export DATABASE_URL=sqlite:///db.sqlite3
```

5. **Execute as migrações:**
```bash
python manage.py migrate
```

6. **Inicie o servidor de desenvolvimento:**
```bash
python manage.py runserver
```

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```ini
# Django
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,capyvagas.example.com
DOMAIN=capyvagas.example.com

# Database
POSTGRES_DB=capyvagas
POSTGRES_USER=capyvagas_user
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# WAHA
WAHA_URL=http://waha:3000
WAHA_SESSION_NAME=capyvagas_session
WAHA_TIMEOUT_SECONDS=5

# Credentials (não sensíveis)
WAHA_DASHBOARD_USERNAME=admin
WHATSAPP_SWAGGER_USERNAME=swagger
BOT_DASHBOARD_USERNAME=admin
BOT_DASHBOARD_PASSWORD=changeme
DJANGO_ADMIN_USERNAME=admin
DJANGO_ADMIN_PASSWORD=changeme
```

### Secrets (secrets/)

Os seguintes secrets devem ser configurados:

- `django_secret_key.txt` - Chave secreta do Django
- `postgres_password.txt` - Senha do PostgreSQL
- `waha_api_key.txt` - API key do WAHA
- `waha_dashboard_password.txt` - Senha do dashboard WAHA
- `waha_swagger_password.txt` - Senha do Swagger WAHA

**⚠️ IMPORTANTE:** Nunca commite arquivos `.txt` em `secrets/`. Use apenas os `.example`.

## 🧪 Testes e Qualidade

### Executar Testes

```bash
# Com Poetry
poetry run pytest

# Com Docker
docker-compose exec backend pytest
```

### Verificação de Código

```bash
# Formatação
poetry run black .

# Linting
poetry run ruff check .

# Type checking
poetry run mypy .

# Tudo de uma vez
make lint  # se Makefile estiver configurado
```

## 📊 Monitoramento

### Health Check

```bash
curl http://localhost/health/
```

Resposta esperada:
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "cache": "healthy"
  }
}
```

### Logs

Os logs são estruturados em JSON para fácil parsing:

```bash
# Ver logs do backend
docker-compose logs -f backend

# Ver logs de todos os serviços
docker-compose logs -f
```

Exemplo de log estruturado:
```json
{
  "timestamp": "2024-11-29T12:00:00.000000Z",
  "level": "info",
  "event": "request_completed",
  "correlation_id": "abc-123-def-456",
  "method": "GET",
  "path": "/health/",
  "status_code": 200,
  "duration_ms": 15.42
}
```

## 🔒 Segurança

### Checklist de Segurança

- [x] Secrets em arquivos separados (Docker Secrets)
- [x] Criptografia de senhas no banco de dados
- [x] HTTPS com Let's Encrypt
- [x] Headers de segurança (HSTS, X-Frame-Options)
- [x] DEBUG=False em produção
- [x] Rate limiting no Traefik
- [x] Connection pooling com health checks
- [x] Logs estruturados para auditoria

### Campos Criptografados

Os seguintes campos são automaticamente criptografados:

- `UserProfile.utfpr_password` - Senha do portal UTFPR
- `BotConfiguration.waha_api_key` - API key do WAHA
- `BotConfiguration.dashboard_password` - Senha do dashboard
- `BotConfiguration.admin_password` - Senha do admin

## 🏗️ Arquitetura do Bot

### Handlers (SOLID)

O bot usa o padrão de handlers para separar responsabilidades:

- **AuthenticationHandler**: Login/logout de usuários
- **JobSearchHandler**: Busca de vagas e seleção de cursos
- **MenuHandler**: Navegação e exibição de menus
- **BaseHandler**: Classe base abstrata

### Fluxo de Conversação

1. Usuário envia mensagem
2. `BotService` identifica ou cria `UserProfile`
3. Mensagem é roteada para o handler apropriado
4. Handler processa e responde
5. Estado é persistido no banco/Redis
6. Interações são logadas

## 📚 Documentação Adicional

- [REFACTORING.md](REFACTORING.md) - Detalhes da refatoração
- [COMO_RODAR_DOCKER.md](COMO_RODAR_DOCKER.md) - Instruções Docker detalhadas
- [secrets/README.md](secrets/README.md) - Gerenciamento de secrets

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

### Padrões de Código

- Use type hints em todas as funções
- Siga os princípios SOLID
- Escreva testes para novas funcionalidades
- Mantenha cobertura de testes > 80%
- Use `black` para formatação
- Passe em `ruff` e `mypy`

## 📝 Licença

Este projeto é desenvolvido como parte de uma Iniciação Científica da UTFPR.

## 👥 Autores

- Equipe CapyVagas - UTFPR Campus Santa Helena

## 🙏 Agradecimentos

- UTFPR - Universidade Tecnológica Federal do Paraná
- Programa de Iniciação Científica
- Comunidade open source

---

**Versão:** 2.0.0 (Refatorado para Produção)  
**Data:** 2024-11-29
