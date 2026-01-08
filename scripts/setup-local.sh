#!/bin/bash

# Script de configuração inicial do CapyVagas
# Este script ajuda a configurar as credenciais localmente

echo "🚀 Configurando CapyVagas para desenvolvimento local"
echo "=================================================="

# Verificar se .env já existe
if [ -f ".env" ]; then
    echo "⚠️  Arquivo .env já existe. Deseja sobrescrever? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "❌ Configuração cancelada."
        exit 1
    fi
fi

# Copiar .env.example para .env
cp .env.example .env
echo "✅ Arquivo .env criado a partir de .env.example"

# Gerar senhas aleatórias
WAHA_API_KEY=$(openssl rand -hex 16)
WAHA_DASHBOARD_PASSWORD=$(openssl rand -base64 12)
SWAGGER_PASSWORD=$(openssl rand -base64 12)
BOT_PASSWORD=$(openssl rand -base64 12)
ADMIN_PASSWORD=$(openssl rand -base64 12)

# Atualizar .env com as senhas geradas
sed -i "s/sua_api_key_aqui/$WAHA_API_KEY/" .env
sed -i "s/sua_senha_aqui/$WAHA_DASHBOARD_PASSWORD/g" .env
sed -i "s/seu_usuario_aqui/admin/g" .env

# Configurar para desenvolvimento
sed -i "s/DEBUG=False/DEBUG=True/" .env
sed -i "s/ALLOWED_HOSTS=localhost,127.0.0.1,capyvagas.example.com/ALLOWED_HOSTS=localhost,127.0.0.1,backend/" .env
sed -i "s/DOMAIN=capyvagas.example.com/DOMAIN=localhost/" .env
sed -i "s/WAHA_SESSION_NAME=capyvagas_session/WAHA_SESSION_NAME=default/" .env

echo ""
echo "📝 Credenciais geradas:"
echo "======================"
echo "🔐 WAHA Dashboard: admin / $WAHA_DASHBOARD_PASSWORD"
echo "🔐 WAHA API Key: $WAHA_API_KEY"
echo "🔐 Swagger: swagger / $SWAGGER_PASSWORD"
echo "🔐 Dashboard Bot: admin / $BOT_PASSWORD"
echo "🔐 Django Admin: admin / $ADMIN_PASSWORD"
echo ""
echo "💾 Senhas salvas em .env"
echo ""
echo "🔒 IMPORTANTE: Não commitar o arquivo .env no Git!"
echo "Ele já está incluído no .gitignore"
echo ""
echo "🚀 Para iniciar os serviços: docker compose up -d"
echo "📊 Dashboard: http://localhost:8000/dashboard/"
echo "📱 WAHA: http://localhost:3000/dashboard/"
