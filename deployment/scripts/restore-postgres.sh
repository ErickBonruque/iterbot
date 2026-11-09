#!/usr/bin/env bash
# ============================================================================
# IterBot - Restaurar o banco a partir de um backup local (.sql.gz)
# ============================================================================
# Uso: deployment/scripts/restore-postgres.sh backups/daily/iterbot_db_AAAAMMDD_HHMMSS.sql.gz
#      (sem argumento: lista os backups disponiveis)
#
# O dump foi gerado com --clean --if-exists: as tabelas atuais sao apagadas e
# recriadas. Para nao haver escrita no meio, o script para backend/worker/beat
# e os sobe de novo no fim. Para baixar um backup da copia fora do host:
#   rclone copy iterbot-offsite:daily/<arquivo> backups/restore/
# ============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
DB_CONTAINER="${DB_CONTAINER:-iterbot_db}"
APP_CONTAINERS=(iterbot_backend iterbot_celery_worker iterbot_celery_beat)

if [ $# -lt 1 ]; then
    echo "Uso: $0 <backup.sql.gz>"
    echo
    echo "Backups locais:"
    ls -1t "${PROJECT_DIR}"/backups/{daily,weekly}/iterbot_db_*.sql.gz 2>/dev/null || echo "  (nenhum)"
    exit 1
fi

BACKUP_FILE="$1"
[ -f "${BACKUP_FILE}" ] || { echo "Arquivo nao encontrado: ${BACKUP_FILE}"; exit 1; }
gzip -t "${BACKUP_FILE}"

DB_USER="$(docker exec "${DB_CONTAINER}" printenv POSTGRES_USER)"
DB_NAME="$(docker exec "${DB_CONTAINER}" printenv POSTGRES_DB)"

echo "Restaurar ${BACKUP_FILE}"
echo "  sobre o banco ${DB_NAME} em ${DB_CONTAINER} (o conteudo atual sera SUBSTITUIDO)"
read -r -p "Digite RESTAURAR para continuar: " answer
[ "${answer}" = "RESTAURAR" ] || { echo "Cancelado."; exit 0; }

restart_apps() { docker start "${APP_CONTAINERS[@]}" >/dev/null 2>&1 || true; }
trap restart_apps EXIT

echo "[$(date -Iseconds)] parando ${APP_CONTAINERS[*]}"
docker stop "${APP_CONTAINERS[@]}" >/dev/null 2>&1 || true

echo "[$(date -Iseconds)] restaurando..."
gunzip -c "${BACKUP_FILE}" \
    | docker exec -i "${DB_CONTAINER}" psql -q -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" >/dev/null

echo "[$(date -Iseconds)] restauracao concluida; subindo os containers da aplicacao"
