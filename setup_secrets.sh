#!/bin/bash

# Script para configurar os secrets do CapyVagas
# Este script cria todos os arquivos de secrets necessários com valores seguros

set -e

SECRETS_DIR="./secrets"

echo "🔐 Configurando secrets do CapyVagas..."
echo ""

# Verificar se o diretório secrets existe
if [ ! -d "$SECRETS_DIR" ]; then
    echo "❌ Erro: Diretório $SECRETS_DIR não encontrado!"
    exit 1
fi

cd "$SECRETS_DIR"

# Função para gerar senha aleatória
generate_password() {
    openssl rand -base64 32 | tr -d '\n'
}

# Função para gerar Django secret key
generate_django_secret() {
    python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key(), end="")'
}

# Configurar Django Secret Key
if [ ! -f "django_secret_key.txt" ]; then
    echo "📝 Gerando django_secret_key.txt..."
    if command -v python3 &> /dev/null; then
        generate_django_secret > django_secret_key.txt
    else
        generate_password > django_secret_key.txt
    fi
    echo "✅ django_secret_key.txt criado"
else
    echo "⏭️  django_secret_key.txt já existe, pulando..."
fi

# Configurar Postgres Password
if [ ! -f "postgres_password.txt" ]; then
    echo "📝 Gerando postgres_password.txt..."
    generate_password > postgres_password.txt
    echo "✅ postgres_password.txt criado"
else
    echo "⏭️  postgres_password.txt já existe, pulando..."
fi

# Configurar WAHA API Key
if [ ! -f "waha_api_key.txt" ]; then
    echo "📝 Gerando waha_api_key.txt..."
    generate_password > waha_api_key.txt
    echo "✅ waha_api_key.txt criado"
else
    echo "⏭️  waha_api_key.txt já existe, pulando..."
fi

# Configurar WAHA Dashboard Password
if [ ! -f "waha_dashboard_password.txt" ]; then
    echo "📝 Gerando waha_dashboard_password.txt..."
    generate_password > waha_dashboard_password.txt
    echo "✅ waha_dashboard_password.txt criado"
else
    echo "⏭️  waha_dashboard_password.txt já existe, pulando..."
fi

# Configurar WAHA Swagger Password
if [ ! -f "waha_swagger_password.txt" ]; then
    echo "📝 Gerando waha_swagger_password.txt..."
    generate_password > waha_swagger_password.txt
    echo "✅ waha_swagger_password.txt criado"
else
    echo "⏭️  waha_swagger_password.txt já existe, pulando..."
fi

cd ..

echo ""
echo "✅ Todos os secrets foram configurados com sucesso!"
echo ""
echo "📋 Resumo dos secrets criados:"
echo "  - django_secret_key.txt"
echo "  - postgres_password.txt"
echo "  - waha_api_key.txt"
echo "  - waha_dashboard_password.txt"
echo "  - waha_swagger_password.txt"
echo ""
echo "⚠️  IMPORTANTE: Mantenha esses arquivos em segredo e nunca os commite no Git!"
echo ""
echo "🚀 Você pode agora executar: docker-compose up -d"
