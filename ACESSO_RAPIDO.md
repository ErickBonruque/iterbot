# 🚀 CapyVagas - Acesso Rápido

## URLs de Acesso

### 📱 WAHA WhatsApp Dashboard
- **URL**: http://localhost:3000/dashboard/
- **Credenciais**: Ver arquivo `.env` local

### 🖥️ Backend Django
- **Dashboard**: http://localhost:8000/dashboard/
- **Admin**: http://localhost:8000/admin/
- **Credenciais**: Ver arquivo `.env` local

### 📊 Monitoramento
- **Traefik**: http://localhost:8080
- **API Docs**: http://localhost:8000/api/docs/
- **WAHA Swagger**: http://localhost:3000/swagger

## Comandos Úteis

```bash
# Verificar status dos containers
docker compose ps

# Verificar logs
docker compose logs -f waha
docker compose logs -f backend

# Reiniciar serviços
docker compose restart waha
docker compose restart backend

# Parar tudo
docker compose down

# Iniciar tudo
docker compose up -d
```

## 🔐 Configurar Credenciais

Se ainda não configurou:

```bash
./scripts/setup-local.sh
```

Este script irá gerar senhas seguras e exibir as credenciais.

## Conectar WhatsApp

1. Acesse: http://localhost:3000/dashboard/
2. Faça login com as credenciais do .env
3. Escaneie o QR Code com o WhatsApp
4. Pronto! O WhatsApp estará conectado ao CapyVagas

## 📚 Documentação Completa
- [Configuração Local](docs/guides/CONFIGURACAO_LOCAL.md)
- [Credenciais Detalhadas](docs/guides/CREDENCIAIS.md)
- [Guia de Instalação](docs/guides/COMO_RODAR_DOCKER.md)
