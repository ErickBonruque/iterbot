# 🚀 Configuração Local - CapyVagas

Este guia explica como configurar o CapyVagas em ambiente de desenvolvimento local com credenciais seguras.

## ⚡ Configuração Rápida

### 1. Execute o script de configuração

```bash
./scripts/setup-local.sh
```

Este script irá:
- Criar o arquivo `.env` com configurações locais
- Gerar senhas aleatórias e seguras
- Configurar as URLs para localhost
- Exibir todas as credenciais geradas

### 2. Inicie os serviços

```bash
docker compose up -d
```

### 3. Acesse os serviços

As credenciais serão exibidas no final do script de configuração.

## 🔐 Configuração Manual

Se preferir configurar manualmente:

### 1. Copie o arquivo de ambiente

```bash
cp .env.example .env
```

### 2. Edite o arquivo `.env`

```bash
nano .env
```

Configure as seguintes variáveis:

```env
# Configurações locais
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,backend
DOMAIN=localhost

# WAHA
WAHA_API_KEY=sua_chave_api_unic_aqui
WAHA_DASHBOARD_USERNAME=seu_usuario
WAHA_DASHBOARD_PASSWORD=sua_senha_forte
WHATSAPP_SWAGGER_USERNAME=swagger
WHATSAPP_SWAGGER_PASSWORD=sua_senha_forte

# Dashboard
BOT_DASHBOARD_USERNAME=seu_usuario
BOT_DASHBOARD_PASSWORD=sua_senha_forte

# Django Admin
DJANGO_ADMIN_USERNAME=seu_usuario
DJANGO_ADMIN_PASSWORD=sua_senha_forte
```

## 🔒 Segurança

### Arquivos Sensíveis

- **`.env`**: Contém todas as senhas e chaves API
  - **NUNCA** commitar este arquivo
  - Já está incluído no `.gitignore`
  - Mantenha-o seguro e compartilhe apenas com equipe confiável

### Senhas Sugeridas

Use senhas fortes com:
- Mínimo 12 caracteres
- Letras maiúsculas e minúsculas
- Números e símbolos
- Evite senhas comuns como "admin123"

### Exemplo de geração de senha segura

```bash
# Gerar senha de 16 caracteres
openssl rand -base64 12
```

## 📁 Estrutura de Arquivos

```
CapyVagas-UTFPR/
├── .env                 # 🔐 Credenciais locais (não commitar)
├── .env.example         # 📝 Template de configuração
├── .gitignore           # 🚫 Arquivos ignorados pelo Git
├── scripts/
│   └── setup-local.sh   # ⚡ Script de configuração rápida
└── secrets/             # 🔐 Segredos Docker (produção)
    ├── django_secret_key.txt
    └── postgres_password.txt
```

## 🐛 Problemas Comuns

### "ALLOWED_HOSTS error"
- Verifique se `backend` está em `ALLOWED_HOSTS` no `.env`
- Reinicie o backend: `docker compose restart backend`

### "WAHA 401 Unauthorized"
- Verifique se `WAHA_API_KEY` está correta no `.env`
- Reinicie os serviços: `docker compose down && docker compose up -d`

### Senha não funciona
- Verifique se o arquivo `.env` está sendo lido
- Use `docker compose exec backend printenv | grep WAHA` para verificar

## 🚀 Comandos Úteis

```bash
# Verificar variáveis de ambiente no container
docker compose exec backend printenv | grep -E "(WAHA|PASSWORD)"

# Reiniciar serviços após mudar .env
docker compose down && docker compose up -d

# Verificar logs
docker compose logs -f backend
docker compose logs -f waha
```

## 📚 Documentação Adicional

- [README Principal](../README.md)
- [Credenciais](../docs/guides/CREDENCIAIS.md)
- [Guia de Instalação Completa](../docs/guides/COMO_RODAR_DOCKER.md)
