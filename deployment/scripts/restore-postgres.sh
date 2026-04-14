#!/bin/bash
# ============================================================================
# CapyVagas - Restaurar Backup PostgreSQL do S3
# ============================================================================
# Uso: ./deployment/scripts/restore-postgres.sh s3://capyvagas-backups/weekly/capyvagas_backup_YYYYMMDD_HHMMSS.sql.gz
# ============================================================================
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Uso: $0 <s3-path>"
    echo "Exemplo: $0 s3://capyvagas-backups/weekly/capyvagas_backup_20260413_020000.sql.gz"
    echo ""
    echo "Backups disponiveis:"
    aws s3 ls "s3://${S3_BACKUP_BUCKET:-capyvagas-backups}/weekly/" --human-readable
    exit 1
fi

S3_PATH="$1"
RESTORE_FILE="/tmp/capyvagas_restore.sql.gz"
DOCKER_BIN=$(command -v docker || echo "/usr/bin/docker")
AWS_BIN=$(command -v aws || echo "/usr/local/bin/aws")
PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/waha_capyvaga}"

if [ -f "${PROJECT_DIR}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_DIR}/.env" | grep -E '^(POSTGRES_USER|POSTGRES_DB)=' | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-capyvagas_user}"
POSTGRES_DB="${POSTGRES_DB:-capyvagas}"

echo "[$(date -Iseconds)] Restaurando backup de: ${S3_PATH}"
echo "  Database: ${POSTGRES_DB}"

read -p "ATENCAO: Isso vai sobrescrever o banco atual. Continuar? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restauracao cancelada."
    exit 0
fi

# Download do S3
${AWS_BIN} s3 cp "${S3_PATH}" "${RESTORE_FILE}" --quiet

# Restaurar no container PostgreSQL
gunzip -c "${RESTORE_FILE}" | ${DOCKER_BIN} exec -i capyvagas_db psql \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}"

# Limpeza
rm -f "${RESTORE_FILE}"

echo "[$(date -Iseconds)] Restauracao concluida."
