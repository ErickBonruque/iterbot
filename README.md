# CapyVagas-UTFPR

> **Assistente de WhatsApp para estudantes da UTFPR**  
> Projeto de Iniciação Científica - Campus Santa Helena

Bot de WhatsApp integrado ao WAHA com dashboard administrativo em Django/DRF. Arquitetura refatorada para produção com foco em segurança, escalabilidade e observabilidade.

## 🌟 Características

- ✅ **Seguro**: Criptografia de dados sensíveis, HTTPS com Let's Encrypt, Docker Secrets
- ✅ **Escalável**: PostgreSQL, Redis, cache distribuído, arquitetura de microserviços
- ✅ **Observável**: Logs estruturados, health checks, métricas em tempo real
- ✅ **Robusto**: Restart policies, connection pooling, tratamento de erros
- ✅ **Manutenível**: SOLID principles, type hints, documentação completa
- ✅ **Testável**: Framework de testes, cobertura de código

## 📁 Estrutura do Projeto

```
CapyVagas-UTFPR/
├── apps/                       # Aplicações Django por domínio
│   ├── bot/                    # Lógica do bot e handlers
│   ├── courses/                # Gerenciamento de cursos
│   ├── users/                  # Perfis de usuários
│   ├── jobs/                   # Buscas e logs de vagas
│   ├── dashboard/              # Interface administrativa
│   └── core/                   # Funcionalidades compartilhadas
├── config/                     # Configurações Django
├── infra/                      # Infraestrutura e integrações
│   ├── jobspy/                 # Integração JobSpy
│   ├── waha/                   # Cliente WAHA
│   ├── security/               # Criptografia e segurança
│   └── traefik/                # Configuração Traefik
├── docker/                     # Dockerfiles e scripts
│   ├── django/                 # Backend Django
│   └── waha/                   # Configuração WAHA
├── deployment/                 # Scripts e configs de deploy
│   ├── scripts/                # Scripts de automação
│   └── configs/                # Configurações de produção
├── docs/                       # Documentação
│   ├── guides/                 # Guias de uso
│   ├── architecture/           # Documentação de arquitetura
│   └── troubleshooting/        # Solução de problemas
├── secrets/                    # Docker secrets (não commitados)
└── waha_bot/                   # Configuração Django
```

## 🚀 Início Rápido

### Pré-requisitos

- Docker e Docker Compose
- Git

### 1. Clone o repositório

```bash
git clone https://github.com/ErickBonruque/CapyVagas-UTFPR.git
cd CapyVagas-UTFPR
```

### 2. Configure os secrets

```bash
./deployment/scripts/setup_secrets.sh
```

Este script gera automaticamente todos os secrets necessários com valores seguros.

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
| **WAHA Dashboard** | http://localhost:3000/dashboard/ | `admin` / `admin123` |
| **Backend Dashboard** | http://localhost:8000/dashboard/ | `admin` / `changeme` |
| **Django Admin** | http://localhost:8000/admin/ | `admin` / `changeme` |
| **API Docs** | http://localhost:8000/api/docs/ | - |
| **WAHA Swagger** | http://localhost:3000/swagger | `swagger` / `admin123` |
| **Traefik Dashboard** | http://localhost:8080 | - |

## 📚 Documentação

### Guias

- **[Instalação Completa](docs/guides/COMO_RODAR_DOCKER.md)** - Guia detalhado de instalação
- **[Credenciais](docs/guides/CREDENCIAIS.md)** - Credenciais de acesso aos serviços
- **[Dashboard](docs/guides/DASHBOARD_DOCUMENTATION.md)** - Documentação do dashboard

### Troubleshooting

- **[WAHA](docs/troubleshooting/WAHA_FIX_DOCUMENTATION.md)** - Solução de problemas do WAHA

### Outros

- **[Secrets](secrets/README.md)** - Como configurar Docker secrets
- **[WAHA Docker](docker/waha/README.md)** - Configuração customizada do WAHA

## 🔧 Desenvolvimento

### Ambiente Local

```bash
# Instalar Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Instalar dependências
poetry install

# Ativar ambiente virtual
poetry shell

# Configurar variáveis
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
docker-compose logs -f waha
docker-compose logs -f backend
```

## 🔐 Segurança

- **Docker Secrets**: Todas as credenciais sensíveis são armazenadas em Docker Secrets
- **HTTPS**: Traefik com Let's Encrypt para certificados automáticos
- **Criptografia**: Dados sensíveis criptografados no banco de dados
- **Autenticação**: Sistema robusto com sessões seguras

## 📊 Monitoramento

### Health Checks

```bash
# Backend
curl http://localhost:8000/health/

# WAHA
curl http://localhost:3000/health

# Banco de dados
docker-compose exec db pg_isready

# Redis
docker-compose exec redis redis-cli ping
```

## 🛠️ Troubleshooting

### WAHA não inicia ou senha não funciona

1. Verifique os logs:
```bash
docker-compose logs waha
```

2. Verifique se os secrets existem:
```bash
ls -la secrets/waha_*.txt
cat secrets/waha_dashboard_password.txt
```

3. Recrie os secrets:
```bash
./deployment/scripts/setup_secrets.sh
```

4. Recrie o container:
```bash
docker-compose stop waha
docker-compose rm -f waha
docker-compose up -d waha
```

### Erro de conexão com banco de dados

```bash
# Verificar se o PostgreSQL está rodando
docker-compose ps db

# Ver logs
docker-compose logs db

# Recriar o banco
docker-compose down
docker-compose up -d db
```

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
