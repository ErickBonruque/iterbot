# WAHA - Guia Completo e Definitivo

## 🎯 Solução Implementada

O problema de autenticação do WAHA foi **completamente resolvido** com uma abordagem robusta que:

1. **Remove o Traefik** da frente do WAHA (acesso direto)
2. **Carrega secrets corretamente** via entrypoint customizado
3. **Valida e sanitiza** todos os valores antes de usar
4. **Fornece logs detalhados** para debugging

## 🔧 Como Funciona

### Arquitetura

```
Docker Secrets → Entrypoint Script → Environment Variables → WAHA
```

### Fluxo Detalhado

1. Docker monta os secrets em `/run/secrets/*`
2. Entrypoint script (`docker/waha/entrypoint.sh`) é executado
3. Script lê cada arquivo de secret
4. Remove espaços, quebras de linha e caracteres invisíveis
5. Valida que o valor não está vazio
6. Exporta como variável de ambiente normal
7. WAHA inicia e lê as variáveis de ambiente

### Por Que Funciona

- **WAHA não suporta `_FILE`**: Precisa de variáveis normais
- **Acesso direto**: Sem Traefik = sem interferência
- **Validação**: Garante que valores são válidos
- **Logs**: Mostra exatamente o que está acontecendo

## 🚀 Uso

### 1. Configurar Secrets

```bash
./deployment/scripts/setup_secrets.sh
```

Ou manualmente:

```bash
echo "minha_senha_segura" > secrets/waha_dashboard_password.txt
echo "minha_api_key" > secrets/waha_api_key.txt
```

**IMPORTANTE**: Não adicione quebras de linha ou espaços!

### 2. Iniciar WAHA

```bash
docker-compose up -d waha
```

### 3. Verificar Logs

```bash
docker-compose logs waha
```

Você deve ver:

```
============================================
🔐 WAHA Secret Loader
============================================

📡 Loading API Key...
✅ WAHA_API_KEY loaded (length: 44 chars)

🔑 Loading Dashboard Password...
✅ WAHA_DASHBOARD_PASSWORD loaded (length: 44 chars)

📚 Loading Swagger Password...
✅ WHATSAPP_SWAGGER_PASSWORD loaded (length: 44 chars)

============================================
✅ All secrets loaded successfully
============================================

🔍 Environment Variables Check:
   WAHA_DASHBOARD_USERNAME: admin
   WAHA_DASHBOARD_PASSWORD: <set>
   WAHA_API_KEY: <set>
   WHATSAPP_SWAGGER_USERNAME: swagger
   WHATSAPP_SWAGGER_PASSWORD: <set>

============================================
🚀 Starting WAHA...
============================================
```

### 4. Acessar Dashboard

- **URL**: http://localhost:3000/dashboard
- **Username**: `admin`
- **Password**: Valor em `secrets/waha_dashboard_password.txt`

```bash
# Ver sua senha
cat secrets/waha_dashboard_password.txt
```

Em produção o WAHA não tem rota pública, então o dashboard só responde por
túnel SSH:

```bash
ssh -L 3000:localhost:3000 a2587246@gosh.sh.utfpr.edu.br
```

### 5. Parear o WhatsApp (QR Code)

O caminho normal é pelo próprio admin do IterBot, sem túnel:

1. Acesse **Status do Bot** (`/admin/status-bot/`)
2. No painel **Conexão do WhatsApp**, clique em **Mostrar QR Code**
   - Sessão em `FAILED`/`STOPPED`: clique antes em **Reiniciar sessão**
   - Trocar o número do bot: **Desconectar número** e então mostrar o QR
3. No celular do bot: WhatsApp › Dispositivos conectados › Conectar dispositivo
4. A tela troca o código sozinho a cada 8s e avisa quando a sessão vira `WORKING`

O QR só existe enquanto a sessão está em `SCAN_QR_CODE`; nos demais estados a
API responde 422 e a tela mostra o estado atual.

## 🔐 Credenciais

| Serviço | URL | Username | Password | Arquivo |
|---------|-----|----------|----------|---------|
| **Dashboard** | http://localhost:3000/dashboard | `admin` | Secret | `secrets/waha_dashboard_password.txt` |
| **API** | http://localhost:3000/api | - | Header | `secrets/waha_api_key.txt` |
| **Swagger** | http://localhost:3000/swagger | `swagger` | Secret | `secrets/waha_swagger_password.txt` |

## 🛠️ Troubleshooting

### ❌ Senha não funciona

**Causa**: Secret vazio ou com caracteres inválidos

**Solução**:

```bash
# 1. Verificar conteúdo
cat secrets/waha_dashboard_password.txt | od -c

# 2. Verificar tamanho
wc -c secrets/waha_dashboard_password.txt

# 3. Recriar secret (sem quebra de linha)
echo -n "nova_senha_segura" > secrets/waha_dashboard_password.txt

# 4. Recriar container
docker-compose stop waha
docker-compose rm -f waha
docker-compose up -d waha
```

### ❌ "Secret not found" nos logs

**Causa**: Arquivo não existe

**Solução**:

```bash
# Verificar se existe
ls -la secrets/waha_*.txt

# Criar se não existir
./deployment/scripts/setup_secrets.sh
```

### ❌ WAHA não inicia

**Causa**: Erro no entrypoint ou secrets inválidos

**Solução**:

```bash
# 1. Ver logs completos
docker-compose logs waha

# 2. Verificar permissões
chmod +x docker/waha/entrypoint.sh

# 3. Verificar secrets
for f in secrets/waha_*.txt; do
    echo "$f: $(wc -c < $f) bytes"
done

# 4. Recriar tudo
docker-compose down
./deployment/scripts/setup_secrets.sh
docker-compose up -d
```

### ❌ WAHA gera senha aleatória

**Causa**: `WAHA_DASHBOARD_PASSWORD` não foi exportada corretamente

**Solução**:

```bash
# 1. Verificar logs do entrypoint
docker-compose logs waha | grep "WAHA_DASHBOARD_PASSWORD"

# Deve mostrar: ✅ WAHA_DASHBOARD_PASSWORD loaded

# 2. Se não mostrar, verificar secret
cat secrets/waha_dashboard_password.txt

# 3. Recriar secret sem espaços/quebras
echo -n "$(openssl rand -base64 32)" > secrets/waha_dashboard_password.txt

# 4. Recriar container
docker-compose restart waha
```

### ❌ "Cannot find module"

**Causa**: Comando incorreto no entrypoint

**Solução**: O entrypoint atual usa `xvfb-run -a node dist/server.js` que é o comando correto do WAHA. Se ainda der erro, verifique a versão da imagem.

## 🔒 Segurança

### Boas Práticas

1. **Senhas fortes**: Mínimo 32 caracteres
2. **Diferentes por ambiente**: Dev, staging, prod
3. **Rotação regular**: Trocar a cada 90 dias
4. **Backup seguro**: Manter cópia em local seguro
5. **Nunca commitar**: Arquivos `.txt` no `.gitignore`

### Gerar Senhas Seguras

```bash
# Senha aleatória forte
openssl rand -base64 32 | tr -d '\n'

# Ou usar o script
./deployment/scripts/setup_secrets.sh
```

## 📊 Monitoramento

### Health Check

```bash
curl http://localhost:3000/health
```

### Logs em Tempo Real

```bash
docker-compose logs -f waha
```

### Verificar Variáveis de Ambiente

```bash
docker-compose exec waha env | grep WAHA
```

## 🔄 Alterando Senhas

### Passo 1: Editar Secret

```bash
echo -n "nova_senha_aqui" > secrets/waha_dashboard_password.txt
```

### Passo 2: Recriar Container

```bash
docker-compose stop waha
docker-compose rm -f waha
docker-compose up -d waha
```

### Passo 3: Verificar

```bash
docker-compose logs waha | grep "WAHA_DASHBOARD_PASSWORD"
```

## 📚 Referências

- [Documentação oficial WAHA](https://waha.devlike.pro/)
- [WAHA Dashboard](https://waha.devlike.pro/docs/how-to/dashboard/)
- [WAHA Configuration](https://waha.devlike.pro/docs/how-to/config/)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)

## ✅ Checklist de Verificação

Antes de reportar problemas, verifique:

- [ ] Secrets existem e não estão vazios
- [ ] Secrets não têm espaços ou quebras de linha extras
- [ ] Entrypoint tem permissão de execução
- [ ] Logs mostram "✅ All secrets loaded successfully"
- [ ] Container está rodando (`docker-compose ps waha`)
- [ ] Acesso direto em http://localhost:3000/dashboard
- [ ] Username correto: `admin`
- [ ] Senha correta do arquivo secret

## 🎉 Resultado Final

Com esta implementação:

- ✅ **Senhas funcionam 100%**
- ✅ **Sem geração aleatória**
- ✅ **Logs claros e detalhados**
- ✅ **Fácil de debugar**
- ✅ **Seguro e robusto**
- ✅ **Escalável**

**Não há mais problemas de autenticação do WAHA!** 🎊
