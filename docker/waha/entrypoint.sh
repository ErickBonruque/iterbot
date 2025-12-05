#!/bin/bash
set -e

# ============================================================================
# WAHA Entrypoint - Robust Secret Loading
# ============================================================================
# This script loads Docker Secrets and exports them as environment variables
# because WAHA doesn't natively support *_FILE suffix variables.
#
# Author: CapyVagas Team
# Last Updated: 2025-12-01
# ============================================================================

echo "============================================"
echo "🔐 WAHA Secret Loader"
echo "============================================"

# Function to load secret from file and export as environment variable.
# Falls back to existing environment variables so the dashboard password can
# be injected via traditional env vars when Docker secrets are not available
# (e.g., during local testing or when running behind an external Traefik
# instance that doesn't mount secrets).
load_secret() {
    local secret_file=$1
    local env_var=$2
    local required=${3:-false}

    if [ -f "$secret_file" ]; then
        local value=$(cat "$secret_file" | tr -d '\n\r' | tr -d ' ')

        if [ -z "$value" ]; then
            echo "⚠️  WARNING: $secret_file exists but is empty!"
            if [ "$required" = "true" ] && [ -z "${!env_var}" ]; then
                echo "❌ ERROR: $env_var is required but empty"
                exit 1
            fi
        else
            export "$env_var"="$value"
            echo "✅ $env_var loaded (length: ${#value} chars)"
            return 0
        fi
    else
        echo "⚠️  WARNING: Secret file $secret_file not found"
    fi

    # Fallback to an existing environment variable if provided
    if [ -n "${!env_var}" ]; then
        local env_value="${!env_var}"
        echo "✅ $env_var sourced from environment (length: ${#env_value} chars)"
        return 0
    fi

    if [ "$required" = "true" ]; then
        echo "❌ ERROR: Required secret $env_var not found in $secret_file or env"
        exit 1
    fi
}

# Load WAHA_API_KEY (required for backend communication)
echo ""
echo "📡 Loading API Key..."
load_secret "/run/secrets/waha_api_key" "WAHA_API_KEY" true

# Load WAHA_DASHBOARD_PASSWORD (required for dashboard login)
echo ""
echo "🔑 Loading Dashboard Password..."
load_secret "/run/secrets/waha_dashboard_password" "WAHA_DASHBOARD_PASSWORD" true

# Load WHATSAPP_SWAGGER_PASSWORD (optional)
echo ""
echo "📚 Loading Swagger Password..."
load_secret "/run/secrets/waha_swagger_password" "WHATSAPP_SWAGGER_PASSWORD" false

echo ""
echo "============================================"
echo "✅ All secrets loaded successfully"
echo "============================================"
echo ""
echo "🔍 Environment Variables Check:"
echo "   WAHA_DASHBOARD_USERNAME: ${WAHA_DASHBOARD_USERNAME:-<not set>}"
echo "   WAHA_DASHBOARD_PASSWORD: ${WAHA_DASHBOARD_PASSWORD:+<set>}"
echo "   WAHA_API_KEY: ${WAHA_API_KEY:+<set>}"
echo "   WHATSAPP_SWAGGER_USERNAME: ${WHATSAPP_SWAGGER_USERNAME:-<not set>}"
echo "   WHATSAPP_SWAGGER_PASSWORD: ${WHATSAPP_SWAGGER_PASSWORD:+<set>}"
echo ""
echo "============================================"
echo "🚀 Starting WAHA..."
echo "============================================"
echo ""

# Start WAHA with the standard command
exec xvfb-run -a node dist/server.js
