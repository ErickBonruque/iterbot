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

# Dominio atual da EC2 (sslip.io baseado no IP publico detectado via metadata)
if [ -z "${DEPLOY_DOMAIN:-}" ]; then
  PUBLIC_IP=$(curl -sf --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 || echo "")
  if [ -n "$PUBLIC_IP" ]; then
    DOMAIN_VALUE="${PUBLIC_IP//./-}.sslip.io"
  else
    echo "[update_env_production] AVISO: nao foi possivel detectar IP publico, usando valor existente" >&2
    DOMAIN_VALUE=$(grep "^DOMAIN=" "$ENV_FILE" | cut -d= -f2 || echo "localhost")
  fi
else
  DOMAIN_VALUE="$DEPLOY_DOMAIN"
fi

set_env EMAIL_PROVIDER "brevo"
set_env EMAIL_FALLBACK_PROVIDER "console"
set_env DEFAULT_FROM_EMAIL "bonruque@alunos.utfpr.edu.br"
set_env DOMAIN "$DOMAIN_VALUE"
set_env PORTAL_BASE_URL "https://${DOMAIN_VALUE}"
# Inclui localhost/127.0.0.1 para permitir o healthcheck do container
# (curl -f http://localhost:8000/health/) sob DEBUG=False.
set_env ALLOWED_HOSTS "${DOMAIN_VALUE},www.${DOMAIN_VALUE},waha.${DOMAIN_VALUE},backend,localhost,127.0.0.1"

echo "[update_env_production] .env normalizado para dominio ${DOMAIN_VALUE}"
