# CapyVagas-UTFPR

Este projeto é desenvolvido como parte de uma Iniciação Científica do campus de Santa Helena da UTFPR.

Bot de WhatsApp integrado ao WAHA com dashboard administrativo em Django/DRF. O repositório está organizado para implantação em contêineres Docker com Traefik como reverse proxy.

## Visão Geral da Arquitetura
- **config/**: carregamento de variáveis de ambiente e objetos de configuração reutilizáveis (WAHA, credenciais do dashboard, flags de debug).
- **apps/**: aplicativos Django separados por domínio (bot, courses, users, dashboard). Lógicas de negócio são concentradas em serviços e seletores para reduzir acoplamento com views.
- **infra/**: integrações externas (WAHA e JobSpy) encapsuladas em clientes e serviços.
- **waha_bot/**: configuração do projeto Django (ASGI/WSGI, URLs, settings).
- **docker/**: definições de build para a aplicação Django.

## Como Rodar
### Dependências locais (sem Docker)
1. Crie um arquivo `.env` com base em `.env.example`.
2. Instale dependências Python (recomendado usar ambiente virtual):
   ```bash
   pip install -r requirements.txt
   ```
3. Aplique migrações, colete arquivos estáticos e suba o servidor de desenvolvimento:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py runserver 0.0.0.0:8000
   ```

### Executar com Docker Compose
1. Construa os serviços:
   ```bash
   docker-compose build
   ```
2. Suba o ambiente completo (Traefik, backend e WAHA):
   ```bash
   docker-compose up
   ```
   O Traefik publica o painel na porta 8080 (`http://localhost:8080`) e encaminha o host `localhost` para o Django (porta 80) e `waha.localhost` para o WAHA.
3. Para encerrar:
   ```bash
   docker-compose down
   ```

## Configuração de Variáveis de Ambiente
Copie `.env.example` para `.env` e ajuste os valores conforme o ambiente:
```ini
DJANGO_SECRET_KEY=dev-secret-key
DEBUG=True
ALLOWED_HOSTS=*
DATABASE_URL=sqlite:///db.sqlite3
WAHA_URL=http://waha:3000
WAHA_API_KEY=dev-api-key
WAHA_SESSION_NAME=dev-session
WAHA_TIMEOUT_SECONDS=5
BOT_DASHBOARD_USERNAME=admin
BOT_DASHBOARD_PASSWORD=password
DJANGO_ADMIN_USERNAME=admin
DJANGO_ADMIN_PASSWORD=admin
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=admin
WHATSAPP_SWAGGER_USERNAME=swagger
WHATSAPP_SWAGGER_PASSWORD=swagger
```

## Fluxo do Bot e Autenticação
- Credenciais de RA/senha são fornecidas pelo usuário via WhatsApp e validadas por `UTFPRAuthService`.
- O vínculo entre telefone e RA é persistido em `UserProfile`.
- O dashboard define URL, token e sessão do WAHA via `/api/bot/configuration/`, armazenando em `BotConfiguration` para uso pelo `BotService`.

## Qualidade de Código
- Lint/format (Black e Ruff configurados em `pyproject.toml`):
  ```bash
  make lint
  ```
- Testes Django:
  ```bash
  python manage.py test
  ```

## Pontos de Atenção
- Configure o webhook do WAHA para `http://<host>/webhook/` ao usar o Traefik.
- O Whitenoise serve os arquivos estáticos coletados em produção, dispensando servidor adicional para static files.
- As rotas do dashboard seguem o namespace padrão do Django Admin e páginas customizadas em `apps/dashboard`.
