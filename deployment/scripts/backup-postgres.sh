#!/bin/bash
# ============================================================================
# IterBot - Backup PostgreSQL para S3
# ============================================================================
# Executado via crontab diariamente (02:00).
# Requer IAM Role attached a EC2 com permissao s3:PutObject no bucket.
#
# Uso manual: ./deployment/scripts/backup-postgres.sh
# Uso com verificacao: ./deployment/scripts/backup-postgres.sh --verify
# ============================================================================
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="iterbot_backup_${TIMESTAMP}.sql.gz"
S3_BUCKET="${S3_BACKUP_BUCKET:-iterbot-utfpr-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-daily}"
S3_PATH="${S3_PREFIX}/${BACKUP_FILE}"
PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/iterbot}"
DOCKER_BIN=$(command -v docker || echo "/usr/bin/docker")
AWS_BIN=$(command -v aws || echo "/usr/local/bin/aws")

# Carregar variaveis do .env se disponivel
if [ -f "${PROJECT_DIR}/.env" ]; then
    set -a
    while IFS='=' read -r key value; do
        case "$key" in
            POSTGRES_USER|POSTGRES_DB|S3_BACKUP_BUCKET|S3_BACKUP_PREFIX)
                export "$key=$value"
                ;;
        esac
    done < <(grep -v '^#' "${PROJECT_DIR}/.env" | grep -E '^(POSTGRES_USER|POSTGRES_DB|S3_BACKUP_BUCKET|S3_BACKUP_PREFIX)=')
    set +a
fi

POSTGRES_USER="${POSTGRES_USER:-iterbot_user}"
POSTGRES_DB="${POSTGRES_DB:-iterbot}"

START_TIME=$(date +%s)

# Verification mode: download and verify most recent backup
if [ "${1:-}" = "--verify" ]; then
    echo "[$(date -Iseconds)] Modo verificacao: baixando backup mais recente..."

    LATEST_BACKUP=$(${AWS_BIN} s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" 2>/dev/null | sort | tail -1 | awk '{print $4}')

    if [ -z "$LATEST_BACKUP" ]; then
        echo "[ERROR] Nenhum backup encontrado em s3://${S3_BUCKET}/${S3_PREFIX}/"
        exit 1
    fi

    LATEST_SIZE=$(${AWS_BIN} s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/${LATEST_BACKUP}" 2>/dev/null | awk '{print $3}')

    echo "  Backup: ${LATEST_BACKUP}"
    echo "  Tamanho S3: ${LATEST_SIZE} bytes"

    ${AWS_BIN} s3 cp "s3://${S3_BUCKET}/${S3_PREFIX}/${LATEST_BACKUP}" "/tmp/${LATEST_BACKUP}" --quiet

    LOCAL_SIZE=$(stat -c%s "/tmp/${LATEST_BACKUP}" 2>/dev/null || stat -f%z "/tmp/${LATEST_BACKUP}" 2>/dev/null)
    echo "  Tamanho local: ${LOCAL_SIZE} bytes"

    if [ "$LOCAL_SIZE" -le 1000 ]; then
        echo "[ERROR] Backup muito pequeno (${LOCAL_SIZE} bytes) — possivelmente vazio ou corrompido"
        rm -f "/tmp/${LATEST_BACKUP}"
        exit 1
    fi

    if ! gzip -t "/tmp/${LATEST_BACKUP}" 2>/dev/null; then
        echo "[ERROR] Backup falhou na verificacao de integridade gzip"
        rm -f "/tmp/${LATEST_BACKUP}"
        exit 1
    fi

    echo "[$(date -Iseconds)] Verificacao concluida: backup integro (${LOCAL_SIZE} bytes)"
    rm -f "/tmp/${LATEST_BACKUP}"
    exit 0
fi

echo "[$(date -Iseconds)] Iniciando backup do PostgreSQL..."
echo "  Database: ${POSTGRES_DB}"
echo "  Destino: s3://${S3_BUCKET}/${S3_PATH}"

# pg_dump dentro do container PostgreSQL
${DOCKER_BIN} exec iterbot_db pg_dump \
    -U "${POSTGRES_USER}" \
    "${POSTGRES_DB}" \
    | gzip > "/tmp/${BACKUP_FILE}"

# File size check: valid PostgreSQL dumps should be > 1000 bytes
FILESIZE=$(stat -c%s "/tmp/${BACKUP_FILE}" 2>/dev/null || stat -f%z "/tmp/${BACKUP_FILE}" 2>/dev/null)
echo "  Tamanho do backup: ${FILESIZE} bytes"

if [ "$FILESIZE" -le 1000 ]; then
    echo "[ERROR] Backup muito pequeno (${FILESIZE} bytes) — possivelmente vazio ou falhou"
    rm -f "/tmp/${BACKUP_FILE}"
    exit 1
fi

# Gzip integrity check
if ! gzip -t "/tmp/${BACKUP_FILE}" 2>/dev/null; then
    echo "[ERROR] Backup falhou na verificacao de integridade gzip"
    rm -f "/tmp/${BACKUP_FILE}"
    exit 1
fi

# Upload para S3 (autenticado por IAM Role)
${AWS_BIN} s3 cp "/tmp/${BACKUP_FILE}" "s3://${S3_BUCKET}/${S3_PATH}" --quiet

# Limpeza local
rm -f "/tmp/${BACKUP_FILE}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "[$(date -Iseconds)] Backup concluido: s3://${S3_BUCKET}/${S3_PATH}"
echo "  Tamanho: ${FILESIZE} bytes | Duracao: ${DURATION}s"

# S3 lifecycle policy (apply once):
# aws s3api put-bucket-lifecycle-configuration \
#   --bucket "${S3_BUCKET}" \
#   --lifecycle-configuration file://deployment/config/s3-lifecycle.json
