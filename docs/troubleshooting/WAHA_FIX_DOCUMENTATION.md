# Configuração do WAHA - Guia Completo

## 📋 Problema Resolvido

O WAHA não suporta nativamente variáveis de ambiente com sufixo `_FILE` (como `WAHA_API_KEY_FILE`). Quando essas variáveis eram usadas, o WAHA as ignorava e gerava senhas aleatórias automaticamente.

Além disso, quando o dashboard era exposto via Traefik, proxies externos não montavam os Docker secrets, o que fazia o WAHA voltar a gerar senhas aleatórias. Agora o entrypoint também aceita variáveis de ambiente tradicionais como fallback (`WAHA_DASHBOARD_PASSWORD`, `WAHA_API_KEY` etc.), mantendo a autenticação mesmo sem secrets montados.

## ✅ Solução Implementada

Criamos um **script entrypoint customizado** que:
1. Lê os Docker Secrets de `/run/secrets/*`
2. Exporta como variáveis de ambiente normais (`WAHA_API_KEY`, `WAHA_DASHBOARD_PASSWORD`)
3. Inicia o WAHA com as credenciais corretas

> Se os secrets não estiverem disponíveis (ex.: Traefik externo), basta definir as variáveis diretamente no `docker-compose.yml` ou `.env` que o entrypoint respeitará o valor.

## 🚀 Como Usar

### 1. Configurar Senhas

**Opção A: Automático**
```bash
./setup_secrets.sh
```

**Opção B: Manual**
```bash
# Dashboard do WAHA
echo "MinhaSenh@Segur@123" > secrets/waha_dashboard_password.txt

# API Key (comunicação backend ↔ WAHA)
echo "MinhaAPIKey456" > secrets/waha_api_key.txt

# Swagger (documentação da API)
echo "SenhaSwagger789" > secrets/waha_swagger_password.txt
```

### 2. Iniciar o WAHA

```bash
docker-compose up -d waha
```

### 3. Verificar Logs

```bash
docker-compose logs -f waha
```

**Você deve ver:**
```
🔐 Carregando secrets do Docker...
✅ WAHA_API_KEY carregado do secret
✅ WAHA_DASHBOARD_PASSWORD carregado do secret
✅ WHATSAPP_SWAGGER_PASSWORD carregado do secret
🚀 Iniciando WAHA...
```

### 4. Acessar o Dashboard

- **URL:** http://localhost:3000
- **Username:** `admin`
- **Password:** Valor definido em `secrets/waha_dashboard_password.txt`

## 🔐 Credenciais

| Serviço | Username | Password | Arquivo |
|---------|----------|----------|---------|
| **Dashboard** | `admin` | Personalizada | `secrets/waha_dashboard_password.txt` |
| **API** | - | Personalizada | `secrets/waha_api_key.txt` |
| **Swagger** | `swagger` | Personalizada | `secrets/waha_swagger_password.txt` |

## 🔧 Arquitetura da Solução

### Fluxo de Funcionamento

```
1. Docker inicia o container WAHA
   ↓
2. Monta os secrets em /run/secrets/*
   ↓
3. Executa /entrypoint.sh (nosso script customizado)
   ↓
4. Script lê os arquivos de secrets
   ↓
5. Exporta como variáveis de ambiente normais
   ↓
6. Inicia o WAHA com o comando padrão
   ↓
7. WAHA lê WAHA_API_KEY, WAHA_DASHBOARD_PASSWORD, etc.
   ↓
8. Autenticação funciona corretamente! ✅
```

### Arquivos Envolvidos

| Arquivo | Descrição |
|---------|-----------|
| `docker/waha/entrypoint.sh` | Script que lê secrets e exporta variáveis |
| `docker-compose.yml` | Configuração do serviço WAHA |
| `secrets/waha_*.txt` | Arquivos com as credenciais |

## 🛠️ Troubleshooting

### ❌ WAHA não inicia

**Verificar logs:**
```bash
docker-compose logs waha
```

**Verificar entrypoint:**
```bash
ls -la docker/waha/entrypoint.sh
# Deve ter permissão de execução (-rwxr-xr-x)
```

**Corrigir permissões:**
```bash
chmod +x docker/waha/entrypoint.sh
docker-compose restart waha
```

### ❌ Senha não funciona

**1. Verificar se o secret existe:**
```bash
cat secrets/waha_dashboard_password.txt
```

**2. Verificar se foi carregado:**
```bash
docker-compose logs waha | grep "WAHA_DASHBOARD_PASSWORD"
# Deve mostrar: ✅ WAHA_DASHBOARD_PASSWORD carregado do secret
```

**3. Verificar espaços em branco:**
```bash
cat secrets/waha_dashboard_password.txt | od -c
# Não deve ter \n ou espaços extras
```

**4. Recriar o container:**
```bash
docker-compose stop waha
docker-compose rm -f waha
docker-compose up -d waha
```

### ❌ "Secret not found" nos logs

**Verificar se os arquivos existem:**
```bash
ls -la secrets/waha_*.txt
```

**Se não existirem, criar:**
```bash
./setup_secrets.sh
```

**Verificar mapeamento no docker-compose.yml:**
```yaml
secrets:
  - waha_api_key
  - waha_dashboard_password
  - waha_swagger_password
```

### ❌ WAHA gera senha aleatória

Isso acontece quando o WAHA não recebe um valor válido em `WAHA_DASHBOARD_PASSWORD`.

**Solução:**
1. Verificar se o entrypoint está sendo executado
2. Verificar se o secret existe e tem conteúdo
3. Recriar o container completamente

```bash
docker-compose down
./setup_secrets.sh
docker-compose up -d
```

## 📝 Alterando Senhas

### Passo 1: Editar o arquivo de secret

```bash
echo "NovaSenha123" > secrets/waha_dashboard_password.txt
```

### Passo 2: Recriar o container

```bash
docker-compose stop waha
docker-compose rm -f waha
docker-compose up -d waha
```

### Passo 3: Verificar

```bash
docker-compose logs waha | grep "carregado"
```

## 🔒 Segurança

### Boas Práticas

- ✅ Use senhas fortes (mínimo 16 caracteres)
- ✅ Nunca commite os arquivos `.txt` no Git
- ✅ Use senhas diferentes para cada ambiente
- ✅ Rotacione as senhas periodicamente

### Gerando Senhas Seguras

```bash
# Senha aleatória forte
openssl rand -base64 32

# Senha com caracteres especiais
openssl rand -base64 32 | tr -d '\n' && echo
```

## 📚 Referências

- [Documentação oficial do WAHA](https://waha.devlike.pro/)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)
- [WAHA Configuration](https://waha.devlike.pro/docs/how-to/config/)

## 🎯 Resumo

Esta solução:
- ✅ Mantém segurança com Docker Secrets
- ✅ Funciona com a API oficial do WAHA
- ✅ Permite personalização fácil de senhas
- ✅ É fácil de manter e debugar
- ✅ Não expõe credenciais no docker-compose.yml
