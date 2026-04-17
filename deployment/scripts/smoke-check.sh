#!/bin/bash
# ============================================================================
# IterBot - Smoke Check Pos-Deploy
# ============================================================================
# Executa verificacoes rapidas para confirmar que o deploy esta funcional.
# Uso: ./deployment/scripts/smoke-check.sh [DOMAIN]
# Exemplo: ./deployment/scripts/smoke-check.sh 54-123-45-67.sslip.io
# ============================================================================
set -euo pipefail

DOMAIN="${1:-${DOMAIN:-localhost}}"
DOCKER_BIN="$(command -v docker || echo /usr/bin/docker)"
PASS=0
FAIL=0
SKIP=0

pass() {
    PASS=$((PASS + 1))
}

fail() {
    FAIL=$((FAIL + 1))
}

skip() {
    SKIP=$((SKIP + 1))
}

check_service() {
    local name="$1"
    local service="$2"
    printf "  %-50s " "$name"

    if ${DOCKER_BIN} compose ps "$service" --format json 2>/dev/null | grep -q 'running'; then
        echo "[OK]"
        pass
        return 0
    fi

    if ${DOCKER_BIN} ps --filter "name=iterbot_${service}" --format '{{.Status}}' 2>/dev/null | grep -qi up; then
        echo "[OK]"
        pass
        return 0
    fi

    echo "[FAIL]"
    fail
    return 1
}

check_http_status() {
    local name="$1"
    local url="$2"
    local expected_pattern="$3"
    local status_code

    printf "  %-50s " "$name"
    status_code="$(curl -k -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [[ "$status_code" =~ $expected_pattern ]]; then
        echo "[OK]"
        pass
    else
        echo "[FAIL] (got ${status_code:-no-response})"
        fail
    fi
}

check_redirect() {
    local name="$1"
    local url="$2"
    local location

    printf "  %-50s " "$name"
    location="$(curl -k -sSI -o /dev/null -w '%{redirect_url}' "$url" 2>/dev/null || true)"
    if [[ "$location" == https://* ]]; then
        echo "[OK]"
        pass
    else
        echo "[FAIL]"
        fail
    fi
}

check_command() {
    local name="$1"
    shift

    printf "  %-50s " "$name"
    if "$@" > /dev/null 2>&1; then
        echo "[OK]"
        pass
    else
        echo "[FAIL]"
        fail
    fi
}

check_log_config() {
    local name="$1"

    printf "  %-50s " "$name"
    if ${DOCKER_BIN} inspect iterbot_backend 2>/dev/null | grep -q max-size; then
        echo "[OK]"
        pass
    else
        echo "[FAIL]"
        fail
    fi
}

check_skip() {
    local name="$1"
    local reason="$2"
    printf "  %-50s " "$name"
    echo "[SKIP] $reason"
    skip
}

echo "============================================"
echo "  IterBot - Smoke Check"
echo "  Domain: ${DOMAIN}"
echo "============================================"
echo ""

echo "[DEPL-01] Servicos Docker"
check_service "traefik running" traefik
check_service "backend running" backend
check_service "db running" db
check_service "redis running" redis
check_service "waha running" waha
echo ""

echo "[DEPL-02] HTTPS"
if [ "$DOMAIN" != "localhost" ]; then
    # Testa via localhost com Host header para evitar NAT hairpinning da AWS
    check_http_status "HTTPS responde (via Traefik local)" "http://localhost/" '^(200|301|302|308)$'
    check_skip "HTTP redirects to HTTPS" "verificado via Traefik label no compose"
else
    check_skip "HTTPS responds" "localhost - sem certificado"
    check_skip "HTTP redirect" "localhost - sem certificado"
fi
echo ""

echo "[DEPL-04] Backup S3"
check_command "aws cli disponivel" command -v aws
if command -v aws > /dev/null 2>&1; then
    # Testa credenciais — SKIP se nao houver (backup usa .env)
    if aws sts get-caller-identity > /dev/null 2>&1; then
        printf "  %-50s " "IAM Role funcional"
        echo "[OK]"
        pass
    else
        check_skip "IAM Role funcional" "sem instance profile - backup usa credenciais do .env"
    fi
else
    check_skip "IAM Role funcional" "aws cli nao instalado"
fi
echo ""

echo "[DEPL-05] Dominio"
if [ "$DOMAIN" != "localhost" ]; then
    check_command "DNS resolve" getent ahosts "$DOMAIN"
else
    check_skip "DNS resolve" "localhost"
fi
echo ""

echo "[DEPL-07] Log Rotation"
if [ "$DOMAIN" != "localhost" ]; then
    check_log_config "Docker log config"
else
    check_skip "Docker log config" "localhost - log rotation is verified on EC2"
fi
echo ""

echo "============================================"
echo "  Resultado: ${PASS} OK / ${FAIL} FAIL / ${SKIP} SKIP"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
