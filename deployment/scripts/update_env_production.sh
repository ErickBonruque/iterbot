#!/usr/bin/env bash
# ============================================================================
# update_env_production.sh
# ----------------------------------------------------------------------------
# Normaliza o .env de producao na EC2, garantindo que as variaveis
# criticas para envio de e-mail e geracao de links estejam corretas.
# Executado a cada deploy pelo workflow .github/workflows/deploy.yml.
# ============================================================================
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERRO: $ENV_FILE nao encontrado" >&2
  exit 1
fi

# Atualiza ou adiciona uma variavel no .env sem duplicar.
# Uso: set_env VAR valor
set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    # Usa | como delimitador para suportar valores com / (URLs)
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

# Dominio atual da EC2 (sslip.io baseado no IP publico)
DOMAIN_VALUE="${DEPLOY_DOMAIN:-98-81-236-180.sslip.io}"

set_env EMAIL_PROVIDER "ses"
set_env DEFAULT_FROM_EMAIL "***REMOVED***"
set_env DOMAIN "$DOMAIN_VALUE"
set_env PORTAL_BASE_URL "https://${DOMAIN_VALUE}"
set_env ALLOWED_HOSTS "${DOMAIN_VALUE},www.${DOMAIN_VALUE},waha.${DOMAIN_VALUE},backend"

echo "[update_env_production] .env normalizado para dominio ${DOMAIN_VALUE}"
