#!/usr/bin/env bash
# ============================================================================
# IterBot - Agenda backup diario + alerta de disco no cron do usuario (sem root)
# ============================================================================
# Idempotente: substitui as linhas marcadas "# iterbot-backup" / "# iterbot-disk".
# Backup as 03:30 (fora do beat: limpeza 02:00, coleta de vagas 07:00);
# alerta de disco a cada 6 h (check-disk-space.sh, limite 85%).
# Uso: deployment/scripts/install-backup-cron.sh ["MIN HORA" do backup]
# ============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SCHEDULE="${1:-30 3}"
MARK="# iterbot-backup"
DISK_MARK="# iterbot-disk"
LINE="${SCHEDULE} * * * ${SCRIPT_DIR}/backup-postgres.sh >> ${PROJECT_DIR}/backups/backup.log 2>&1 ${MARK}"
DISK_LINE="15 */6 * * * ${SCRIPT_DIR}/check-disk-space.sh >> ${PROJECT_DIR}/backups/disk.log 2>&1 ${DISK_MARK}"

mkdir -p "${PROJECT_DIR}/backups"
chmod 700 "${PROJECT_DIR}/backups"
command -v crontab >/dev/null || { echo "crontab nao encontrado (instale o pacote cron)"; exit 1; }

{
    crontab -l 2>/dev/null | grep -v -F -e "${MARK}" -e "${DISK_MARK}" || true
    echo "${LINE}"
    echo "${DISK_LINE}"
} | crontab -

echo "Agendado:"
crontab -l | grep -F -e "${MARK}" -e "${DISK_MARK}"
