#!/bin/bash
# ============================================================================
# CapyVagas - Smoke Check Pos-Deploy
# ============================================================================
# Executa verificacoes rapidas para confirmar que o deploy esta funcional.
# Uso: ./deployment/scripts/smoke-check.sh [DOMAIN]
# Exemplo: ./deployment/scripts/smoke-check.sh 54-123-45-67.sslip.io
# ============================================================================
set -e

DOMAIN="${1:-${DOMAIN:-localhost}}"
DOCKER_BIN=$(command -v docker || echo "/usr/bin/docker")
PASS=0
FAIL=0
SKIP=0

check() {
    local name="$1"
    local cmd="$2"
    printf "  %-50s " "$name"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "[OK]"
        ((PASS++))
    else
        echo "[FAIL]"
        ((FAIL++))
    fi
}

skip() {
    local name="$1"
    local reason="$2"
    printf "  %-50s " "$name"
    echo "[SKIP] $reason"
    ((SKIP++))
}

echo "============================================"
echo "  CapyVagas - Smoke Check"
echo "  Domain: ${DOMAIN}"
echo "============================================"
echo ""

# DEPL-01: Servicos Docker rodando
echo "[DEPL-01] Servicos Docker"
check "traefik running" "${DOCKER_BIN} compose ps traefik --format json 2>/dev/null | grep -q running || ${DOCKER_BIN} ps --filter name=capyvagas_traefik --format '{{.Status}}' | grep -qi up"
check "backend running" "${DOCKER_BIN} compose ps backend --format json 2>/dev/null | grep -q running || ${DOCKER_BIN} ps --filter name=capyvagas_backend --format '{{.Status}}' | grep -qi up"
check "db running" "${DOCKER_BIN} compose ps db --format json 2>/dev/null | grep -q running || ${DOCKER_BIN} ps --filter name=capyvagas_db --format '{{.Status}}' | grep -qi up"
check "redis running" "${DOCKER_BIN} compose ps redis --format json 2>/dev/null | grep -q running || ${DOCKER_BIN} ps --filter name=capyvagas_redis --format '{{.Status}}' | grep -qi up"
check "waha running" "${DOCKER_BIN} compose ps waha --format json 2>/dev/null | grep -q running || ${DOCKER_BIN} ps --filter name=capyvagas_waha --format '{{.Status}}' | grep -qi up"
echo ""

# DEPL-02: HTTPS valido
echo "[DEPL-02] HTTPS"
if [ "$DOMAIN" != "localhost" ]; then
    check "HTTPS responds 200" "curl -sSf -o /dev/null -w '%{http_code}' https://${DOMAIN}/ 2>/dev/null | grep -qE '(200|301|302)'"
    check "HTTP redirects to HTTPS" "curl -sS -o /dev/null -w '%{redirect_url}' http://${DOMAIN}/ 2>/dev/null | grep -qi https"
else
    skip "HTTPS responds" "localhost - sem certificado"
    skip "HTTP redirect" "localhost - sem certificado"
fi
echo ""

# DEPL-04: Backup S3
echo "[DEPL-04] Backup S3"
check "aws cli disponivel" "command -v aws"
if command -v aws > /dev/null 2>&1; then
    check "IAM Role funcional" "aws sts get-caller-identity"
else
    skip "IAM Role" "aws cli nao instalado"
fi
echo ""

# DEPL-05: Dominio sslip.io
echo "[DEPL-05] Dominio"
if [ "$DOMAIN" != "localhost" ]; then
    check "DNS resolve" "curl -sS -o /dev/null -w '%{http_code}' http://${DOMAIN}/ 2>/dev/null | grep -qE '[0-9]'"
else
    skip "DNS resolve" "localhost"
fi
echo ""

# DEPL-07: Log rotation
echo "[DEPL-07] Log Rotation"
check "Docker log config" "${DOCKER_BIN} inspect capyvagas_backend 2>/dev/null | grep -q max-size"
echo ""

# Resultado
echo "============================================"
echo "  Resultado: ${PASS} OK / ${FAIL} FAIL / ${SKIP} SKIP"
echo "============================================"

if [ $FAIL -gt 0 ]; then
    exit 1
fi
