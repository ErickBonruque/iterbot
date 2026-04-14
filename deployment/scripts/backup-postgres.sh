#!/bin/bash
# ============================================================================
# CapyVagas - Backup PostgreSQL para S3
# ============================================================================
# Executado via crontab semanalmente (domingo 02:00).
# Requer IAM Role attached a EC2 com permissao s3:PutObject no bucket.
#
# Uso manual: ./deployment/scripts/backup-postgres.sh
# ============================================================================
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="capyvagas_backup_${TIMESTAMP}.sql.gz"
S3_BUCKET="${S3_BACKUP_BUCKET:-capyvagas-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-weekly}"
S3_PATH="${S3_PREFIX}/${BACKUP_FILE}"
PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/waha_capyvaga}"
DOCKER_BIN=$(command -v docker || echo "/usr/bin/docker")
AWS_BIN=$(command -v aws || echo "/usr/local/bin/aws")

# Carregar variaveis do .env se disponivel
if [ -f "${PROJECT_DIR}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_DIR}/.env" | grep -E '^(POSTGRES_USER|POSTGRES_DB|S3_BACKUP_BUCKET|S3_BACKUP_PREFIX)=' | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-capyvagas_user}"
POSTGRES_DB="${POSTGRES_DB:-capyvagas}"

echo "[$(date -Iseconds)] Iniciando backup do PostgreSQL..."
echo "  Database: ${POSTGRES_DB}"
echo "  Destino: s3://${S3_BUCKET}/${S3_PATH}"

# pg_dump dentro do container PostgreSQL
${DOCKER_BIN} exec capyvagas_db pg_dump \
    -U "${POSTGRES_USER}" \
    "${POSTGRES_DB}" \
    | gzip > "/tmp/${BACKUP_FILE}"

FILESIZE=$(stat -c%s "/tmp/${BACKUP_FILE}" 2>/dev/null || stat -f%z "/tmp/${BACKUP_FILE}" 2>/dev/null)
echo "  Tamanho do backup: ${FILESIZE} bytes"

# Upload para S3 (autenticado por IAM Role)
${AWS_BIN} s3 cp "/tmp/${BACKUP_FILE}" "s3://${S3_BUCKET}/${S3_PATH}" --quiet

# Limpeza local
rm -f "/tmp/${BACKUP_FILE}"

echo "[$(date -Iseconds)] Backup concluido: s3://${S3_BUCKET}/${S3_PATH}"
