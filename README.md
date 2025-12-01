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
│   ├── courses/             # Gerenciamento de cursos
│   ├── users/               # Perfis de usuários
│   ├── jobs/                # Buscas e logs de vagas
│   ├── dashboard/           # Interface administrativa
│   └── core/                # Funcionalidades compartilhadas
├── config/                  # Configurações e variáveis de ambiente
├── infra/                   # Infraestrutura e integrações
│   ├── jobspy/              # Integração JobSpy
│   ├── waha/                # Cliente WAHA
│   ├── security/            # Criptografia e segurança
│   └── traefik/             # Configuração Traefik
├── docker/                  # Dockerfiles e scripts
│   ├── django/              # Backend Django
│   └── waha/                # Configuração customizada WAHA
├── secrets/                 # Docker secrets (não commitados)
└── docs/                    # Documentação do projeto
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

### 1. Clone o repositório

```bash
git clone https://github.com/ErickBonruque/CapyVagas-UTFPR.git
cd CapyVagas-UTFPR
```

### 2. Configure os secrets

**Opção A: Automático (Recomendado)**
```bash
./setup_secrets.sh
```

**Opção B: Manual**
```bash
# Gerar valores seguros
echo "$(openssl rand -base64 32)" > secrets/django_secret_key.txt
echo "$(openssl rand -base64 32)" > secrets/postgres_password.txt
echo "$(openssl rand -base64 32)" > secrets/waha_api_key.txt
echo "$(openssl rand -base64 32)" > secrets/waha_dashboard_password.txt
echo "$(openssl rand -base64 32)" > secrets/waha_swagger_password.txt
```

### 3. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite .env conforme necessário
```

### 4. Inicie os serviços

```bash
docker-compose up -d
```

### 5. Execute as migrações

```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

### 6. Acesse os serviços

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| **Dashboard Bot** | http://localhost:8000/dashboard/ | Ver `CREDENCIAIS.md` |
| **Django Admin** | http://localhost:8000/admin/ | Superuser criado |
| **WAHA Dashboard** | http://localhost:3000 | Ver `WAHA_FIX_DOCUMENTATION.md` |
| **API Docs** | http://localhost:8000/api/docs/ | - |

## 📚 Documentação

| Arquivo | Descrição |
|---------|-----------|
| **[COMO_RODAR_DOCKER.md](COMO_RODAR_DOCKER.md)** | Guia completo de instalação e configuração com Docker |
| **[CREDENCIAIS.md](CREDENCIAIS.md)** | Credenciais de acesso aos serviços |
| **[WAHA_FIX_DOCUMENTATION.md](WAHA_FIX_DOCUMENTATION.md)** | Configuração e troubleshooting do WAHA |
| **[DASHBOARD_DOCUMENTATION.md](DASHBOARD_DOCUMENTATION.md)** | Documentação completa do dashboard |
| **[secrets/README.md](secrets/README.md)** | Como configurar Docker secrets |
| **[docker/waha/README.md](docker/waha/README.md)** | Configuração customizada do WAHA |

## 🔧 Desenvolvimento

### Ambiente Local (sem Docker)

```bash
# Instalar Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Instalar dependências
poetry install

# Ativar ambiente virtual
poetry shell

# Configurar banco de dados local
export DATABASE_URL="postgresql://user:pass@localhost:5432/capyvagas"
export REDIS_URL="redis://localhost:6379/0"

# Executar migrações
python manage.py migrate

# Iniciar servidor
python manage.py runserver
```

### Testes

```bash
# Executar todos os testes
docker-compose exec backend pytest

# Com cobertura
docker-compose exec backend pytest --cov=apps --cov-report=html

# Testes específicos
docker-compose exec backend pytest apps/bot/tests/
```

### Logs

```bash
# Ver logs de todos os serviços
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f backend
docker-compose logs -f waha
docker-compose logs -f db
```

## 🛠️ Troubleshooting

### WAHA não inicia ou gera senhas aleatórias

Consulte **[WAHA_FIX_DOCUMENTATION.md](WAHA_FIX_DOCUMENTATION.md)** para solução completa.

### Erro de conexão com banco de dados

```bash
# Verificar se o PostgreSQL está rodando
docker-compose ps db

# Ver logs do banco
docker-compose logs db

# Recriar o banco
docker-compose down
docker-compose up -d db
```

### Problemas com secrets

```bash
# Verificar se os secrets existem
ls -la secrets/*.txt

# Recriar secrets
./setup_secrets.sh

# Recriar containers
docker-compose down
docker-compose up -d
```

## 🔐 Segurança

- **Secrets**: Todas as credenciais sensíveis são armazenadas em Docker Secrets
- **HTTPS**: Traefik com Let's Encrypt para certificados automáticos
- **Criptografia**: Dados sensíveis criptografados no banco de dados
- **Autenticação**: Sistema de autenticação robusto com sessões seguras

## 📊 Monitoramento

### Health Checks

```bash
# Backend
curl http://localhost:8000/health/

# Banco de dados
docker-compose exec db pg_isready

# Redis
docker-compose exec redis redis-cli ping
```

### Métricas

O dashboard fornece métricas em tempo real:
- Total de usuários
- Mensagens processadas
- Buscas de vagas realizadas
- Status do sistema

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto é parte de uma Iniciação Científica da UTFPR Campus Santa Helena.

## 👥 Autores

- **Erick Bonruque** - Desenvolvedor Principal
- **Orientação**: UTFPR Campus Santa Helena

## 🙏 Agradecimentos

- UTFPR Campus Santa Helena
- Comunidade WAHA
- Comunidade Django
