# 📊 Documentação Completa do Dashboard WAHA Bot

## 🎯 Visão Geral

Dashboard moderno e completo para gerenciamento e monitoramento do bot WAHA integrado com JobSpy e autenticação UTFPR.

---

## 📐 Arquitetura do Sistema

### Stack Tecnológica

| Camada | Tecnologia | Versão |
|--------|------------|--------|
| **Backend** | Django | 5.2.8 |
| **API REST** | Django REST Framework | 3.16+ |
| **Banco de Dados** | SQLite (dev) / PostgreSQL (prod) | - |
| **Frontend** | Tailwind CSS + HTMX + Alpine.js | Latest CDN |
| **Gráficos** | Chart.js | 4.4.0 |
| **Filtros API** | django-filter | 25.2 |

### Estrutura de Pastas

```
apps/
├── bot/
│   ├── models.py              # BotHealthCheck, BotMetrics, InteractionLog
│   ├── health.py              # BotHealthMonitor (sistema de monitoramento)
│   └── ...
├── courses/
│   └── models.py              # Course, SearchTerm
├── dashboard/
│   ├── views.py               # Views do dashboard
│   ├── api_views.py           # ViewSets da API REST
│   ├── api_urls.py            # Rotas da API
│   ├── serializers.py         # Serializers DRF
│   └── templates/dashboard/
│       ├── base_modern.html
│       ├── home_modern.html
│       ├── bot_status.html
│       ├── courses_modern.html
│       └── interactions_modern.html
└── ...
```

---

## 🗄️ Modelo de Dados

### 1. Course (Cursos)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | AutoField | ID único |
| `name` | CharField(100) | Nome do curso |
| `code` | CharField(20) | Código do curso (ex: COENS) |
| `description` | TextField | Descrição detalhada |
| `is_active` | BooleanField | Curso ativo no sistema |
| `order` | IntegerField | Ordem de exibição |
| `created_at` | DateTimeField | Data de criação |
| `updated_at` | DateTimeField | Última atualização |

**Métodos:**
- `__str__()`: Retorna o nome do curso
- **Meta:** `ordering = ['order', 'name']`

---

### 2. SearchTerm (Termos de Busca)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | AutoField | ID único |
| `course` | ForeignKey(Course) | Curso associado |
| `term` | CharField(100) | Termo de busca para JobSpy |
| `is_default` | BooleanField | Termo ativo/padrão |
| `priority` | IntegerField | Prioridade (maior = mais importante) |
| `created_at` | DateTimeField | Data de criação |
| `updated_at` | DateTimeField | Última atualização |

**Constraints:**
- `unique_together = [['course', 'term']]`
- **Meta:** `ordering = ['-priority', 'term']`

---

### 3. BotHealthCheck (Verificações de Saúde)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | AutoField | ID único |
| `status` | CharField(20) | online / offline / error |
| `response_time` | FloatField | Tempo de resposta em ms |
| `error_message` | TextField | Mensagem de erro (se houver) |
| `session_status` | CharField(50) | Status da sessão WAHA |
| `created_at` | DateTimeField | Timestamp da verificação |

**Índices:**
- `created_at` (desc)
- `status`

---

### 4. BotMetrics (Métricas Personalizadas)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | AutoField | ID único |
| `metric_name` | CharField(100) | Nome da métrica |
| `value` | FloatField | Valor da métrica |
| `metadata` | JSONField | Metadados adicionais |
| `created_at` | DateTimeField | Timestamp |

**Índices:**
- `(metric_name, created_at)` composto

---

### 5. InteractionLog (Logs de Interação)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | AutoField | ID único |
| `user` | ForeignKey(UserProfile) | Usuário |
| `message_content` | TextField | Conteúdo da mensagem |
| `message_type` | CharField(10) | SENT / RECEIVED |
| `session_id` | CharField(100) | ID da sessão WAHA |
| `metadata` | JSONField | Metadados da mensagem |
| `created_at` | DateTimeField | Timestamp |

**Índices:**
- `created_at` (desc)
- `(user, created_at)` composto
- `message_type`

---

## 🔌 API REST - Endpoints

### Base URL: `/api/`

### 1. **Bot Status**

#### `GET /api/bot/status/`
Retorna status atual do bot + métricas agregadas

**Response:**
```json
{
  "status": "online",
  "response_time": 145.23,
  "session_status": "WORKING",
  "last_check": "2025-11-28T23:30:00Z",
  "uptime_percentage": 98.5,
  "avg_response_time": 150.2,
  "total_checks": 1440,
  "error_count": 12
}
```

#### `POST /api/bot/status/test/`
Testa o bot agora (verifica status + envia mensagem de teste)

**Response:**
```json
{
  "success": true,
  "message": "Bot está operacional",
  "details": { ... }
}
```

#### `GET /api/bot/status/history/?hours=24`
Histórico de verificações

**Query Params:**
- `hours` (int): Período em horas (default: 24)

---

### 2. **Courses (Cursos)**

#### `GET /api/courses/`
Lista todos os cursos (com paginação)

**Query Params:**
- `is_active` (bool): Filtrar por status
- `search` (str): Buscar por nome, código ou descrição
- `ordering` (str): Ordenar por campo (ex: `name`, `-created_at`)

**Response:**
```json
{
  "count": 15,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Engenharia de Software",
      "code": "COENS",
      "is_active": true,
      "order": 0,
      "search_terms_count": 5
    }
  ]
}
```

#### `POST /api/courses/`
Criar novo curso

**Request Body:**
```json
{
  "name": "Ciência da Computação",
  "code": "COCOM",
  "description": "Curso de graduação em CC",
  "is_active": true,
  "order": 0
}
```

#### `GET /api/courses/{id}/`
Detalhes de um curso (incluindo search_terms)

#### `PUT /api/courses/{id}/`
Atualizar curso

#### `DELETE /api/courses/{id}/`
Deletar curso

#### `POST /api/courses/{id}/toggle_active/`
Alternar status ativo/inativo

**Response:**
```json
{
  "id": 1,
  "is_active": false,
  "message": "Curso desativado com sucesso"
}
```

#### `POST /api/courses/bulk_delete/`
Deletar múltiplos cursos

**Request Body:**
```json
{
  "ids": [1, 2, 3]
}
```

---

### 3. **SearchTerms (Termos de Busca)**

#### `GET /api/terms/`
Lista todos os termos

**Query Params:**
- `course` (int): Filtrar por curso
- `is_default` (bool): Filtrar por status

#### `GET /api/terms/by_course/?course_id=1`
Termos de um curso específico

#### `POST /api/terms/`
Criar novo termo

**Request Body:**
```json
{
  "course": 1,
  "term": "Python Developer",
  "is_default": true,
  "priority": 10
}
```

#### `PUT /api/terms/{id}/`
Atualizar termo

#### `DELETE /api/terms/{id}/`
Deletar termo

#### `POST /api/terms/{id}/toggle_default/`
Alternar status ativo/inativo

#### `POST /api/terms/reorder/`
Reordenar termos

**Request Body:**
```json
{
  "order": [
    {"id": 1, "priority": 10},
    {"id": 2, "priority": 5}
  ]
}
```

---

### 4. **Interactions (Histórico de Interações)**

#### `GET /api/interactions/`
Lista interações (paginado, somente leitura)

**Query Params:**
- `user` (int): Filtrar por usuário
- `message_type` (str): SENT ou RECEIVED
- `search` (str): Buscar em conteúdo, telefone ou RA

**Response:**
```json
{
  "count": 1250,
  "results": [
    {
      "id": 100,
      "user": 5,
      "user_phone": "5541999999999@c.us",
      "user_ra": "a1234567",
      "message_content": "Olá, gostaria de ver vagas",
      "message_type": "RECEIVED",
      "session_id": "default",
      "created_at": "2025-11-28T20:15:00Z"
    }
  ]
}
```

#### `GET /api/interactions/stats/?days=7`
Estatísticas de interações

**Response:**
```json
{
  "total_interactions": 1250,
  "messages_received": 650,
  "messages_sent": 600,
  "unique_users": 45,
  "period_days": 7
}
```

#### `POST /api/interactions/clear/`
Limpar histórico (com filtros opcionais)

**Request Body:**
```json
{
  "user_id": 5,       // Opcional: limpar apenas deste usuário
  "days": 30          // Opcional: limpar logs com mais de N dias
}
```

**Response:**
```json
{
  "message": "120 log(s) de interação deletado(s) com sucesso",
  "count": 120
}
```

---

## 🎨 Interface do Dashboard

### Páginas Implementadas

#### 1. **Home (`/dashboard/`)**
- **Cards de Estatísticas:**
  - Cursos ativos
  - Total de interações
  - Usuários únicos
  - Uptime do bot (24h)
- **Últimas interações** (10 mais recentes)
- **Status rápido do bot**

#### 2. **Status do Bot (`/dashboard/status/`)**
- **Status em destaque:**
  - Indicador visual (online/offline/erro)
  - Tempo de resposta
  - Uptime
  - Contagem de erros
- **Botão "Testar Bot Agora"**
- **Métricas por período:**
  - Última hora
  - Últimas 24 horas
  - Últimos 7 dias
- **Tabela de histórico de verificações**

#### 3. **Cursos (`/dashboard/courses/`)**
- **Grid de cards** (responsivo)
  - Nome, código, descrição
  - Status (ativo/inativo)
  - Quantidade de termos
- **Ações por curso:**
  - Ativar/Desativar
  - Editar
  - Deletar
  - Gerenciar termos
- **Botão "Novo Curso"**

#### 4. **Interações (`/dashboard/interactions/`)**
- **Filtros:**
  - Período (1d, 7d, 30d, tudo)
  - Tipo (recebidas/enviadas/todas)
  - Busca livre
- **Cards de estatísticas:**
  - Total de mensagens
  - Recebidas
  - Enviadas
- **Lista paginada** com:
  - Telefone e RA do usuário
  - Conteúdo da mensagem
  - Tipo e timestamp
- **Botão "Limpar Histórico"** (com confirmação)

---

## 🔧 Sistema de Monitoramento (`BotHealthMonitor`)

### Localização
`apps/bot/health.py`

### Métodos Principais

#### `check_bot_status()`
Verifica o status do bot fazendo requisição ao WAHA.

**Retorna:**
```python
{
    'status': 'online' | 'offline' | 'error',
    'response_time': 145.23,  # em ms
    'session_status': 'WORKING',
    'last_check': datetime,
    'error_message': None | str
}
```

**Comportamento:**
- Faz GET em `/api/sessions/{session_name}`
- Mede tempo de resposta
- Registra no banco (`BotHealthCheck`)
- Salva no cache (60s)

---

#### `get_metrics_summary(hours=24)`
Calcula métricas agregadas de um período.

**Retorna:**
```python
{
    'uptime_percentage': 98.5,
    'avg_response_time': 150.2,
    'total_checks': 1440,
    'error_count': 12,
    'last_error': 'Timeout ao conectar com WAHA'
}
```

---

#### `test_bot_now()`
Executa teste completo do bot.

---

#### `clean_old_health_checks(days=7)`
Remove registros antigos (manutenção).

---

## 🚀 Como Usar

### 1. Acessar o Dashboard

```bash
# Abrir no navegador
http://localhost:8000/dashboard/
```

### 2. Gerenciar Cursos

**Via Dashboard Web:**
1. Ir para `/dashboard/courses/`
2. Clicar em "Novo Curso"
3. Preencher formulário no admin Django
4. Voltar ao dashboard para gerenciar termos

**Via API:**
```bash
# Criar curso
curl -X POST http://localhost:8000/api/courses/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engenharia de Software",
    "code": "COENS",
    "is_active": true
  }'

# Listar cursos
curl http://localhost:8000/api/courses/
```

### 3. Adicionar Termos de Busca

**Via API:**
```bash
curl -X POST http://localhost:8000/api/terms/ \
  -H "Content-Type: application/json" \
  -d '{
    "course": 1,
    "term": "Python Developer",
    "is_default": true,
    "priority": 10
  }'
```

### 4. Verificar Status do Bot

**Via Dashboard:**
- Indicador em tempo real no header (atualiza a cada 30s via HTMX)
- Página dedicada: `/dashboard/status/`

**Via API:**
```bash
curl http://localhost:8000/api/bot/status/
```

### 5. Visualizar Interações

**Via Dashboard:**
- `/dashboard/interactions/`
- Aplicar filtros por período, tipo e busca

**Via API:**
```bash
# Listar interações
curl 'http://localhost:8000/api/interactions/?message_type=RECEIVED&search=python'

# Estatísticas
curl 'http://localhost:8000/api/interactions/stats/?days=7'
```

---

## ⚙️ Configuração Avançada

### Variáveis de Ambiente (`.env`)

```env
# Sessão WAHA (já configurado)
WAHA_SESSION_NAME=default
WAHA_URL=http://waha:3000
WAHA_API_KEY=waha_secret_key

# Django REST Framework (opcional)
# Adicionar autenticação em produção
```

### Autenticação da API (TODO em Produção)

Atualmente a API está com `AllowAny`. Para produção:

```python
# Em apps/dashboard/api_views.py
from rest_framework.permissions import IsAuthenticated

class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # Alterar
```

### Configurar Health Checks Automáticos

Criar um comando Django personalizado:

```python
# apps/bot/management/commands/check_bot_health.py
from django.core.management.base import BaseCommand
from apps.bot.health import BotHealthMonitor

class Command(BaseCommand):
    def handle(self, *args, **options):
        monitor = BotHealthMonitor()
        status = monitor.check_bot_status()
        self.stdout.write(f"Bot status: {status['status']}")
```

**Executar via Cron:**
```bash
*/5 * * * * cd /app && python manage.py check_bot_health
```

---

## 📊 Checklist de Conformidade

### ✅ Requisitos Atendidos

| Requisito | Status | Implementação |
|-----------|--------|---------------|
| **1. Status do Bot** | ✅ | Dashboard + API `/api/bot/status/` |
| - Indicadores (online/offline) | ✅ | Visual + JSON |
| - Última resposta | ✅ | `created_at` em `BotHealthCheck` |
| - Erros recentes | ✅ | `error_message` + contagem |
| - Latência média | ✅ | `avg_response_time` calculado |
| - Botão "testar bot agora" | ✅ | `POST /api/bot/status/test/` |
| **2. CRUD de Cursos** | ✅ | Dashboard + API `/api/courses/` |
| - Listar | ✅ | `GET /api/courses/` |
| - Criar | ✅ | `POST /api/courses/` |
| - Editar | ✅ | `PUT /api/courses/{id}/` |
| - Arquivar/Excluir | ✅ | `DELETE` + toggle_active |
| - Campos mínimos | ✅ | name, code, description, is_active, order |
| **3. CRUD de Termos JobSpy** | ✅ | API `/api/terms/` |
| - Adicionar | ✅ | `POST /api/terms/` |
| - Editar | ✅ | `PUT /api/terms/{id}/` |
| - Remover | ✅ | `DELETE /api/terms/{id}/` |
| - Reordenar | ✅ | `POST /api/terms/reorder/` |
| **4. Cache de Interações** | ✅ | Model `InteractionLog` |
| - Salvar mensagens | ✅ | user, content, type, timestamp |
| - Filtros (número, data) | ✅ | Query params na API |
| - Exclusão de histórico | ✅ | `POST /api/interactions/clear/` |
| - Confirmação de exclusão | ✅ | Via JavaScript (confirm) |
| **5. Painel Moderno** | ✅ | Tailwind + HTMX + Alpine.js |
| - Layout responsivo | ✅ | Grid system do Tailwind |
| - Componentes modernos | ✅ | Cards, tabelas, modais |
| - Navegação (sidebar) | ✅ | Sidebar colapsável |
| - Microinterações | ✅ | Alpine.js (toasts, modals) |

---

## 🎯 Próximos Passos (Melhorias Futuras)

1. **Autenticação e Autorização**
   - Adicionar login no dashboard
   - Implementar permissões por role (admin, operador, viewer)

2. **Gráficos Avançados**
   - Gráfico de uptime ao longo do tempo (Chart.js)
   - Distribuição de mensagens por hora do dia
   - Top termos de busca mais efetivos

3. **Notificações em Tempo Real**
   - WebSockets para atualização live do status
   - Alertas quando bot ficar offline

4. **Export de Dados**
   - Exportar interações em CSV/Excel
   - Relatórios PDF de métricas

5. **Testes Automatizados**
   - Unit tests para models e serializers
   - Integration tests para API
   - E2E tests com Playwright

6. **Otimizações de Performance**
   - Redis como cache backend
   - Celery para health checks assíncronos
   - Database indexes adicionais

---

## 📚 Referências Técnicas

- **Django REST Framework**: https://www.django-rest-framework.org/
- **Tailwind CSS**: https://tailwindcss.com/
- **HTMX**: https://htmx.org/
- **Alpine.js**: https://alpinejs.dev/
- **Chart.js**: https://www.chartjs.org/

---

## 👨‍💻 Desenvolvido por

Sistema de Dashboard profissional para o projeto WAHA IterBot - Bot de vagas integrado com UTFPR.

**Data:** Novembro 2025
**Versão:** 1.0.0
