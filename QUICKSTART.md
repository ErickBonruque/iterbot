# 🚀 CapyVagas - Guia de Início Rápido

## Configuração em 3 Passos

### 1️⃣ Setup Inicial

```bash
# Clone o repositório
git clone https://github.com/ErickBonruque/CapyVagas-UTFPR.git
cd CapyVagas-UTFPR

# Configure secrets e valide ambiente
make setup
```

### 2️⃣ Inicie os Serviços

```bash
make start
```

### 3️⃣ Acesse o Sistema

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| **WAHA Dashboard** | http://localhost:3000/dashboard | `admin` / `cat secrets/waha_dashboard_password.txt` |
| **Backend Dashboard** | http://localhost:8000/dashboard/ | Ver docs/guides/CREDENCIAIS.md |
| **Django Admin** | http://localhost:8000/admin/ | Criar com `make createsuperuser` |

## Comandos Úteis

```bash
# Ver status dos serviços
make status

# Ver logs do WAHA
make logs-waha

# Ver logs do backend
make logs-backend

# Verificar saúde dos serviços
make health

# Reiniciar WAHA
make waha-restart

# Parar tudo
make stop
```

## Troubleshooting

### WAHA não funciona?

```bash
# 1. Ver logs
make logs-waha

# 2. Verificar senha
cat secrets/waha_dashboard_password.txt

# 3. Reiniciar
make waha-restart
```

### Backend não funciona?

```bash
# 1. Ver logs
make logs-backend

# 2. Executar migrações
make migrate

# 3. Reiniciar
make restart
```

## Documentação Completa

- **[README.md](README.md)** - Documentação principal
- **[WAHA Guide](docs/troubleshooting/WAHA_COMPLETE_GUIDE.md)** - Guia completo do WAHA
- **[Architecture](docs/architecture/OVERVIEW.md)** - Arquitetura do sistema

## Suporte

Se encontrar problemas, consulte:
1. [docs/troubleshooting/](docs/troubleshooting/)
2. Logs dos serviços (`make logs`)
3. Validação de ambiente (`make validate`)
