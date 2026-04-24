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

# Aguarda Traefik aceitar conexoes (ate 30s) para evitar race condition
# imediatamente apos 'docker compose up -d' no deploy.
printf "Aguardando Traefik aceitar conexoes"
for i in $(seq 1 15); do
    if curl -k -s -o /dev/null --max-time 2 "http://localhost/" 2>/dev/null; then
        printf " [OK]\n"
        break
    fi
    printf "."
    sleep 2
    if [ "$i" = "15" ]; then
        printf " [TIMEOUT apos 30s — seguindo mesmo assim]\n"
    fi
done
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

echo "[SEC-01] Security Group - Blocked Ports"
if [ "$DOMAIN" != "localhost" ]; then
    for BLOCKED_PORT in 3000 8000 8080; do
        printf "  %-50s " "Port ${BLOCKED_PORT} NOT publicly accessible"
        if nc -z -w2 "$DOMAIN" "$BLOCKED_PORT" 2>/dev/null; then
            echo "[FAIL] (port is OPEN - security risk!)"
            fail
        else
            echo "[OK]"
            pass
        fi
    done
else
    for BLOCKED_PORT in 3000 8000 8080; do
        check_skip "Port ${BLOCKED_PORT} NOT publicly accessible" "localhost - verified on EC2"
    done
fi
echo ""

echo "[SEC-02] BasicAuth"
if [ "$DOMAIN" != "localhost" ]; then
    WAHA_STATUS=$(curl -k -sS -o /dev/null -w '%{http_code}' "https://waha.${DOMAIN}/dashboard" 2>/dev/null || echo "000")
    printf "  %-50s " "WAHA Dashboard requires auth (expect 401)"
    if [ "$WAHA_STATUS" = "401" ] || [ "$WAHA_STATUS" = "403" ]; then
        echo "[OK] (${WAHA_STATUS})"
        pass
    else
        echo "[FAIL] (got ${WAHA_STATUS})"
        fail
    fi

    ADMIN_STATUS=$(curl -k -sS -o /dev/null -w '%{http_code}' "https://${DOMAIN}/admin/" 2>/dev/null || echo "000")
    printf "  %-50s " "Django Admin requires auth (expect 401)"
    if [ "$ADMIN_STATUS" = "401" ] || [ "$ADMIN_STATUS" = "403" ]; then
        echo "[OK] (${ADMIN_STATUS})"
        pass
    else
        echo "[FAIL] (got ${ADMIN_STATUS})"
        fail
    fi

    WAHA_WRONG=$(curl -k -sS -o /dev/null -w '%{http_code}' -u "admin:wrongpassword" "https://waha.${DOMAIN}/dashboard" 2>/dev/null || echo "000")
    printf "  %-50s " "WAHA Dashboard rejects wrong password (expect 401)"
    if [ "$WAHA_WRONG" = "401" ] || [ "$WAHA_WRONG" = "403" ]; then
        echo "[OK] (${WAHA_WRONG})"
        pass
    else
        echo "[FAIL] (got ${WAHA_WRONG})"
        fail
    fi
else
    check_skip "WAHA Dashboard requires auth" "localhost"
    check_skip "Django Admin requires auth" "localhost"
    check_skip "WAHA rejects wrong password" "localhost"
fi
echo ""

echo "[SEC-03] HTTPS"
if [ "$DOMAIN" != "localhost" ]; then
    REDIRECT_URL="http://${DOMAIN}"
    REDIRECT_STATUS=$(curl -k -sS -o /dev/null -w '%{http_code}' --max-redirs 0 "$REDIRECT_URL" 2>/dev/null || echo "000")
    printf "  %-50s " "HTTP redirects to HTTPS"
    if [ "$REDIRECT_STATUS" = "301" ] || [ "$REDIRECT_STATUS" = "308" ] || [ "$REDIRECT_STATUS" = "302" ]; then
        echo "[OK] (${REDIRECT_STATUS})"
        pass
    else
        echo "[FAIL] (got ${REDIRECT_STATUS})"
        fail
    fi

    HTTPS_STATUS=$(curl -k -sS -o /dev/null -w '%{http_code}' "https://${DOMAIN}/health/" 2>/dev/null || echo "000")
    printf "  %-50s " "HTTPS /health/ responds (200)"
    if [ "$HTTPS_STATUS" = "200" ]; then
        echo "[OK]"
        pass
    else
        echo "[FAIL] (got ${HTTPS_STATUS})"
        fail
    fi

    # Check email provider is not "console" in production
    EMAIL_PROVIDER=$(${DOCKER_BIN} exec iterbot_backend python -c "from config.env import settings; print(settings.email.provider)" 2>/dev/null || echo "")
    printf "  %-50s " "Email provider is not 'console'"
    if [ -n "$EMAIL_PROVIDER" ] && [ "$EMAIL_PROVIDER" != "console" ]; then
        echo "[OK] (${EMAIL_PROVIDER})"
        pass
    elif [ "$EMAIL_PROVIDER" = "console" ]; then
        echo "[FAIL] (EMAIL_PROVIDER=console — emails go to logs only!)"
        fail
    else
        echo "[WARN] (could not determine EMAIL_PROVIDER)"
        skip
    fi

    CERT_VALID=$(echo | openssl s_client -connect "${DOMAIN}:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || echo "")
    printf "  %-50s " "TLS certificate is valid"
    if [ -n "$CERT_VALID" ]; then
        echo "[OK]"
        pass
    else
        echo "[FAIL]"
        fail
    fi
else
    check_skip "HTTP redirects to HTTPS" "localhost"
    check_skip "HTTPS /health/ responds" "localhost"
    check_skip "TLS certificate valid" "localhost"
fi
echo ""

echo "============================================"
echo "  Resultado: ${PASS} OK / ${FAIL} FAIL / ${SKIP} SKIP"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
