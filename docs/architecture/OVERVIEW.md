# Arquitetura do CapyVagas

## Visão Geral

O CapyVagas é uma aplicação de microserviços construída com Django, PostgreSQL, Redis, WAHA e Traefik. A arquitetura foi projetada para ser escalável, segura e fácil de manter.

## Componentes

### 1. Backend (Django + DRF)

**Responsabilidades:**
- API REST para frontend e integrações
- Lógica de negócio do bot
- Gerenciamento de usuários e cursos
- Integração com WAHA e JobSpy

**Tecnologias:**
- Django 4.x
- Django REST Framework
- PostgreSQL (via psycopg2)
- Redis (cache e sessões)

**Endpoints principais:**
- `/api/` - API REST
- `/admin/` - Django Admin
- `/dashboard/` - Dashboard customizado
- `/health/` - Health check

### 2. WAHA (WhatsApp HTTP API)

**Responsabilidades:**
- Integração com WhatsApp Web
- Envio e recebimento de mensagens
- Gerenciamento de sessões do WhatsApp

**Acesso:**
- **Dashboard**: http://localhost:3000/dashboard
- **API**: http://localhost:3000/api
- **Swagger**: http://localhost:3000/swagger

**Configuração:**
- Acesso direto (sem proxy) para evitar problemas de autenticação
- Secrets carregados via entrypoint customizado
- Health checks configurados

### 3. PostgreSQL

**Responsabilidades:**
- Armazenamento de dados persistentes
- Usuários, cursos, vagas, logs

**Configuração:**
- Versão: 15-alpine
- Volume persistente
- Health checks
- Senha via Docker Secret

### 4. Redis

**Responsabilidades:**
- Cache de dados frequentes
- Armazenamento de sessões
- Filas de tarefas (futuro)

**Configuração:**
- Versão: 7-alpine
- Persistência com AOF
- Política de eviction: allkeys-lru
- Limite de memória: 256MB

### 5. Traefik

**Responsabilidades:**
- Reverse proxy
- Load balancing
- HTTPS automático (Let's Encrypt)
- Roteamento baseado em host

**Configuração:**
- Backend: Proxied
- WAHA: Direct access (sem proxy)
- Dashboard: http://localhost:8080

## Fluxo de Dados

### 1. Mensagem do WhatsApp

```
WhatsApp → WAHA → Webhook → Backend → Processamento → Resposta → WAHA → WhatsApp
```

### 2. Busca de Vagas

```
Usuário → WhatsApp → WAHA → Backend → JobSpy → Backend → WAHA → WhatsApp
```

### 3. Dashboard

```
Admin → Browser → Traefik → Backend → PostgreSQL/Redis → Backend → Browser
```

## Segurança

### Docker Secrets

Todas as credenciais sensíveis são armazenadas em Docker Secrets:
- `django_secret_key` - Chave secreta do Django
- `postgres_password` - Senha do PostgreSQL
- `waha_api_key` - API key do WAHA
- `waha_dashboard_password` - Senha do dashboard WAHA
- `waha_swagger_password` - Senha do Swagger WAHA

### Rede

- Todos os serviços na mesma rede Docker (`web`)
- Comunicação interna via nomes de serviço
- Apenas portas necessárias expostas ao host

### HTTPS

- Traefik com Let's Encrypt automático
- Redirecionamento HTTP → HTTPS
- Certificados renovados automaticamente

## Escalabilidade

### Horizontal

- Backend: Pode ser escalado com múltiplas réplicas
- Redis: Pode ser configurado em cluster
- PostgreSQL: Pode usar replicação read-only

### Vertical

- Recursos ajustáveis via Docker Compose
- Limites de memória e CPU configuráveis

## Monitoramento

### Health Checks

Todos os serviços têm health checks configurados:
- Backend: `/health/`
- WAHA: `/health`
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`

### Logs

- Logs estruturados em JSON (produção)
- Logs coloridos (desenvolvimento)
- Níveis: ERROR, WARNING, INFO, DEBUG

## Backup e Recuperação

### Dados

- PostgreSQL: Volume `postgres_data`
- Redis: Volume `redis_data`
- WAHA Sessions: Volume `waha_sessions`

### Secrets

- Manter backup seguro dos arquivos em `secrets/`
- Usar diferentes secrets por ambiente

## Ambientes

### Desenvolvimento

```bash
docker-compose up
```

### Produção

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Próximos Passos

1. **Kubernetes**: Migrar para K8s para melhor orquestração
2. **Observabilidade**: Adicionar Prometheus + Grafana
3. **CI/CD**: Implementar pipeline automatizado
4. **Testes**: Aumentar cobertura de testes
5. **Documentação**: Adicionar mais diagramas e exemplos
