#!/usr/bin/env bash
# ============================================================================
# IterBot - Alerta de disco cheio (host gosh)
# ============================================================================
# O disco de 19 GB e o gargalo do host (imagem do WAHA ~4 GB + 3 imagens da
# aplicacao + build cache). Se o uso de / passar de DISK_THRESHOLD (padrao 85%),
# manda alerta por e-mail via `manage.py send_ops_alert` (ALERT_EMAIL).
# Agendado junto com o backup por install-backup-cron.sh.
# ============================================================================
set -Eeuo pipefail

DISK_THRESHOLD="${DISK_THRESHOLD:-85}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-iterbot_backend}"

usage="$(df -P / | awk 'NR==2 {gsub("%", "", $5); print $5}')"
echo "[$(date -Iseconds)] uso do disco: ${usage}% (limite ${DISK_THRESHOLD}%)"

if [ "${usage}" -ge "${DISK_THRESHOLD}" ]; then
    body="Disco do host $(hostname) em ${usage}% (limite ${DISK_THRESHOLD}%).

$(df -h /)

$(docker system df 2>/dev/null || true)

Para liberar: docker builder prune -f && docker image prune -f"
    docker exec "${BACKEND_CONTAINER}" python manage.py send_ops_alert \
        --subject "Disco em ${usage}% no host" --body "${body}" >/dev/null \
        || echo "AVISO: nao consegui enviar o alerta por e-mail"
    exit 1
fi
