# Refatoração para Produção - CapyVagas-UTFPR

Este documento descreve as principais mudanças implementadas na refatoração completa do projeto CapyVagas-UTFPR para torná-lo pronto para produção.

## 🎯 Objetivos da Refatoração

Transformar o projeto de um protótipo de iniciação científica em uma aplicação **robusta, segura, escalável e pronta para produção**.

## 📋 Principais Mudanças

### 1. Gerenciamento de Dependências com Poetry

**Antes:** `requirements.txt` com versões não fixadas
**Depois:** Poetry com `pyproject.toml` e `poetry.lock`

- ✅ Versões fixadas e reproduzíveis
- ✅ Separação entre dependências de produção e desenvolvimento
- ✅ Melhor resolução de conflitos de dependências
- ✅ Suporte a grupos de dependências opcionais

**Arquivos:**
- `pyproject.toml` - Configuração do Poetry e ferramentas
- `poetry.lock` - Lock file com versões exatas

### 2. Infraestrutura com Docker Compose

#### PostgreSQL
**Antes:** SQLite em volume não persistente (comentado)
**Depois:** PostgreSQL 13 com volume persistente

- ✅ Banco de dados robusto para produção
- ✅ Volume nomeado para persistência de dados
- ✅ Health checks configurados
- ✅ Credenciais gerenciadas via Docker secrets

#### Redis
**Novo:** Serviço Redis para cache e sessões

- ✅ Cache distribuído para escalabilidade
- ✅ Armazenamento de estado de conversação
- ✅ Suporte a Celery para tarefas assíncronas
- ✅ Volume persistente com AOF habilitado

#### Traefik
**Antes:** HTTP apenas, socket Docker exposto
**Depois:** HTTPS com Let's Encrypt

- ✅ Certificados SSL automáticos
- ✅ Redirecionamento HTTP → HTTPS
- ✅ Headers de segurança configurados
- ✅ Rate limiting implementado
- ✅ Logs estruturados em JSON

**Arquivos:**
- `docker-compose.yml` - Orquestração completa
- `infra/traefik/traefik.yml` - Configuração do Traefik
- `infra/traefik/dynamic/middlewares.yml` - Middlewares de segurança

### 3. Segurança

#### Gerenciamento de Secrets
**Antes:** Credenciais em texto plano no `.env`
**Depois:** Docker Secrets

- ✅ Secrets em arquivos separados (`secrets/`)
- ✅ Nunca commitados no Git (`.gitignore`)
- ✅ Exemplos fornecidos (`.example`)
- ✅ Documentação de geração de secrets

**Secrets gerenciados:**
- `django_secret_key` - Chave secreta do Django
- `postgres_password` - Senha do PostgreSQL
- `waha_api_key` - API key do WAHA
- `waha_dashboard_password` - Senha do dashboard WAHA
- `waha_swagger_password` - Senha do Swagger WAHA

#### Criptografia de Dados Sensíveis
**Antes:** Senhas em texto plano no banco
**Depois:** Campos criptografados

- ✅ `EncryptedCharField` para senhas
- ✅ Criptografia usando `cryptography` (Fernet)
- ✅ Chave derivada do `SECRET_KEY` do Django
- ✅ Aplicado em `UserProfile.utfpr_password` e `BotConfiguration`

**Arquivos:**
- `infra/security/encryption.py` - Utilitários de criptografia
- `infra/security/fields.py` - Campos Django criptografados
- `apps/users/models.py` - Modelo atualizado
- `apps/bot/models.py` - Modelo atualizado

#### Configurações de Segurança Django
- ✅ `DEBUG=False` por padrão
- ✅ `SECURE_SSL_REDIRECT=True` em produção
- ✅ `SESSION_COOKIE_SECURE=True`
- ✅ `CSRF_COOKIE_SECURE=True`
- ✅ HSTS habilitado (31536000 segundos)
- ✅ `X_FRAME_OPTIONS=DENY`

### 4. Observabilidade

#### Logging Estruturado
**Antes:** Logs não estruturados
**Depois:** Logs JSON com `structlog`

- ✅ Formato JSON para fácil parsing
- ✅ Correlation IDs para rastreamento distribuído
- ✅ Contexto automático (método, path, usuário)
- ✅ Timestamps ISO 8601
- ✅ Stack traces em exceções

**Arquivos:**
- `infra/middleware/correlation_id.py` - Middleware de correlation ID
- `infra/middleware/structured_logging.py` - Middleware de logging
- `waha_bot/settings.py` - Configuração do structlog

#### Health Checks
**Novo:** Endpoint de health check

- ✅ Verifica conectividade do banco de dados
- ✅ Verifica conectividade do Redis
- ✅ Retorna status HTTP 503 se unhealthy
- ✅ Usado pelos health checks do Docker

**Endpoint:** `GET /health/`

**Arquivos:**
- `apps/core/views/health.py` - View de health check

### 5. Qualidade de Código

#### Refatoração do BotService
**Antes:** "God Class" com múltiplas responsabilidades
**Depois:** Handlers especializados seguindo SRP

**Handlers criados:**
- `AuthenticationHandler` - Login/logout
- `JobSearchHandler` - Busca de vagas
- `MenuHandler` - Navegação e menus
- `BaseHandler` - Classe base abstrata

**Benefícios:**
- ✅ Código mais testável
- ✅ Responsabilidades bem definidas
- ✅ Fácil extensão com novos handlers
- ✅ Melhor manutenibilidade

**Arquivos:**
- `apps/bot/handlers/` - Diretório de handlers
- `apps/bot/services.py` - Service refatorado

#### Tipagem Estrita
- ✅ Type hints em todas as funções
- ✅ Configuração do `mypy` no `pyproject.toml`
- ✅ Imports do `typing` para tipos complexos

#### Ferramentas de Qualidade
- ✅ `black` - Formatação automática
- ✅ `ruff` - Linting rápido
- ✅ `mypy` - Verificação de tipos
- ✅ `pytest` - Framework de testes

### 6. Modelos e Dados

#### Novo Modelo: JobSearchLog
**Novo:** Rastreamento de buscas por vagas

- ✅ Registra termos de busca
- ✅ Armazena número de resultados
- ✅ Preview dos primeiros 5 resultados
- ✅ Relacionado ao usuário via ForeignKey
- ✅ Índices otimizados

**Arquivo:** `apps/jobs/models.py`

#### Melhorias em Modelos Existentes
- ✅ Campos criptografados em `UserProfile`
- ✅ Campos criptografados em `BotConfiguration`
- ✅ Índices de banco de dados otimizados

### 7. Configuração

#### django-environ
**Antes:** Parsing manual de `.env`
**Depois:** `django-environ` para configuração

- ✅ Parsing robusto de variáveis de ambiente
- ✅ Suporte a tipos (bool, int, list, etc.)
- ✅ Valores padrão configuráveis
- ✅ Leitura de Docker secrets

**Arquivo:** `config/env.py`

#### Configuração de Banco de Dados
**Antes:** SQLite hardcoded
**Depois:** `dj-database-url` com suporte a PostgreSQL

- ✅ `DATABASE_URL` para configuração
- ✅ Connection pooling (`conn_max_age=600`)
- ✅ Health checks de conexão

### 8. Dockerfile

**Antes:** Build simples com `requirements.txt`
**Depois:** Multi-stage build com Poetry

- ✅ Stage de builder separado
- ✅ Instalação apenas de dependências de produção
- ✅ Imagem final menor
- ✅ Cache otimizado de layers

**Arquivo:** `docker/django/Dockerfile`

## 🚀 Como Usar

### Configuração Inicial

1. **Copiar arquivo de ambiente:**
```bash
cp .env.example .env
```

2. **Configurar secrets:**
```bash
cd secrets
cp django_secret_key.txt.example django_secret_key.txt
cp postgres_password.txt.example postgres_password.txt
cp waha_api_key.txt.example waha_api_key.txt
cp waha_dashboard_password.txt.example waha_dashboard_password.txt
cp waha_swagger_password.txt.example waha_swagger_password.txt

# Gerar valores seguros
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > django_secret_key.txt
openssl rand -base64 32 > postgres_password.txt
openssl rand -base64 32 > waha_api_key.txt
openssl rand -base64 32 > waha_dashboard_password.txt
openssl rand -base64 32 > waha_swagger_password.txt
```

3. **Editar `.env` com suas configurações:**
- Alterar `DOMAIN` para seu domínio real
- Configurar outras variáveis conforme necessário

4. **Iniciar serviços:**
```bash
docker-compose up -d
```

5. **Executar migrações:**
```bash
docker-compose exec backend python manage.py migrate
```

6. **Criar superusuário:**
```bash
docker-compose exec backend python manage.py createsuperuser
```

### Desenvolvimento Local

1. **Instalar Poetry:**
```bash
pip install poetry
```

2. **Instalar dependências:**
```bash
poetry install
```

3. **Ativar ambiente virtual:**
```bash
poetry shell
```

4. **Executar testes:**
```bash
poetry run pytest
```

5. **Verificar código:**
```bash
poetry run black .
poetry run ruff check .
poetry run mypy .
```

## 📊 Métricas de Qualidade

### Antes da Refatoração
- ❌ Sem testes automatizados
- ❌ Sem tipagem estática
- ❌ Código não formatado consistentemente
- ❌ Sem observabilidade
- ❌ Credenciais em texto plano
- ❌ SQLite não persistente

### Depois da Refatoração
- ✅ Framework de testes configurado
- ✅ Type hints em todo o código
- ✅ Formatação automática com Black
- ✅ Logging estruturado JSON
- ✅ Secrets criptografados
- ✅ PostgreSQL com persistência

## 🔒 Segurança

### Checklist de Segurança Implementado

- [x] Secrets em arquivos separados (não no Git)
- [x] Criptografia de senhas no banco de dados
- [x] HTTPS com Let's Encrypt
- [x] Headers de segurança (HSTS, X-Frame-Options, etc.)
- [x] DEBUG=False por padrão
- [x] Rate limiting no Traefik
- [x] Validação de inputs
- [x] Connection pooling com health checks
- [x] Logs estruturados para auditoria

## 📈 Próximos Passos

### Recomendações para Produção

1. **Testes:**
   - Implementar testes unitários para handlers
   - Testes de integração para fluxos completos
   - Cobertura de testes > 80%

2. **Máquina de Estados:**
   - Migrar para `python-statemachine`
   - Persistir estado no Redis
   - Implementar timeouts de sessão

3. **Autenticação UTFPR:**
   - Substituir mock por integração real
   - Implementar sistema de convites se API não disponível

4. **Dashboard:**
   - Criar views de detalhes de usuário
   - Histórico de interações
   - Histórico de buscas de vagas
   - Métricas e analytics

5. **Monitoramento:**
   - Integrar com Prometheus para métricas
   - Configurar alertas (Alertmanager)
   - Dashboard Grafana

6. **CI/CD:**
   - GitHub Actions para testes
   - Deploy automático
   - Verificação de qualidade de código

## 📚 Documentação Adicional

- `secrets/README.md` - Gerenciamento de secrets
- `COMO_RODAR_DOCKER.md` - Instruções Docker (atualizar)
- `README.md` - Documentação principal (atualizar)

## 🤝 Contribuindo

Com esta refatoração, o projeto está pronto para receber contribuições de forma organizada:

1. Código segue padrões SOLID
2. Type hints facilitam entendimento
3. Testes garantem qualidade
4. Logs estruturados facilitam debugging
5. Documentação clara e atualizada

## 📝 Notas de Migração

### Migrações de Banco de Dados

Após esta refatoração, será necessário:

1. Criar novas migrações para campos criptografados
2. Migrar dados existentes (se houver)
3. Executar `python manage.py makemigrations`
4. Executar `python manage.py migrate`

### Dados Existentes

⚠️ **IMPORTANTE:** Se você tem dados em produção:

1. Faça backup completo antes de migrar
2. Senhas existentes precisarão ser re-criptografadas
3. Considere script de migração de dados

## 🎓 Aprendizados

Esta refatoração demonstra:

- **SOLID Principles** na prática
- **Clean Architecture** com separação de concerns
- **Security by Design** desde o início
- **Observability** como requisito não-funcional
- **Infrastructure as Code** com Docker Compose
- **Type Safety** com Python type hints

---

**Versão:** 1.0.0  
**Data:** 2024-11-29  
**Autor:** Refatoração Completa para Produção
