#!/bin/bash
set -e

# Script de entrypoint para o WAHA
# Este script lê os secrets do Docker e os exporta como variáveis de ambiente normais
# porque o WAHA não suporta nativamente o sufixo _FILE

echo "🔐 Carregando secrets do Docker..."

# Função para ler secret e exportar como variável de ambiente
load_secret() {
    local secret_file=$1
    local env_var=$2
    
    if [ -f "$secret_file" ]; then
        export "$env_var"=$(cat "$secret_file")
        echo "✅ $env_var carregado do secret"
    else
        echo "⚠️  Secret $secret_file não encontrado"
    fi
}

# Carregar WAHA_API_KEY do secret
load_secret "/run/secrets/waha_api_key" "WAHA_API_KEY"

# Carregar WAHA_DASHBOARD_PASSWORD do secret
load_secret "/run/secrets/waha_dashboard_password" "WAHA_DASHBOARD_PASSWORD"

# Carregar WHATSAPP_SWAGGER_PASSWORD do secret
load_secret "/run/secrets/waha_swagger_password" "WHATSAPP_SWAGGER_PASSWORD"

echo "🚀 Iniciando WAHA..."

# Executar o comando padrão do WAHA
# O WAHA usa xvfb-run para rodar o Node.js com display virtual
exec xvfb-run -a node dist/server.js
