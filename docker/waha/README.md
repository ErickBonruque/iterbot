# WAHA - Configuração Customizada

Este diretório contém o script de inicialização customizado para o container WAHA.

## 📄 Arquivo

### `entrypoint.sh`

Script que resolve o problema de autenticação do WAHA lendo Docker Secrets e exportando como variáveis de ambiente normais.

## 🔧 Como Funciona

```bash
#!/bin/bash
# 1. Lê /run/secrets/waha_api_key
# 2. Exporta como WAHA_API_KEY
# 3. Repete para todas as credenciais
# 4. Inicia o WAHA com comando padrão
```

## 🚀 Uso

O script é montado automaticamente via `docker-compose.yml`:

```yaml
waha:
  entrypoint: ["/entrypoint.sh"]
  volumes:
    - ./docker/waha/entrypoint.sh:/entrypoint.sh:ro
```

## 🔐 Secrets Suportados

| Secret | Variável | Descrição |
|--------|----------|-----------|
| `waha_api_key` | `WAHA_API_KEY` | API key para autenticação |
| `waha_dashboard_password` | `WAHA_DASHBOARD_PASSWORD` | Senha do dashboard |
| `waha_swagger_password` | `WHATSAPP_SWAGGER_PASSWORD` | Senha do Swagger |

## 📝 Logs

Ao iniciar, o script exibe:

```
🔐 Carregando secrets do Docker...
✅ WAHA_API_KEY carregado do secret
✅ WAHA_DASHBOARD_PASSWORD carregado do secret
✅ WHATSAPP_SWAGGER_PASSWORD carregado do secret
🚀 Iniciando WAHA...
```

## ⚠️ Importante

- Mantenha a permissão de execução: `chmod +x entrypoint.sh`
- Não modifique sem entender o impacto
- As senhas devem estar em `secrets/*.txt`

## 🛠️ Troubleshooting

### Script não executa

```bash
chmod +x docker/waha/entrypoint.sh
docker-compose restart waha
```

### Secrets não carregados

```bash
ls -la ../../secrets/waha_*.txt
```

## 📚 Documentação

Para mais detalhes, consulte: `WAHA_FIX_DOCUMENTATION.md` (raiz do projeto)
