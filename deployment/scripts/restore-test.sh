#!/usr/bin/env bash
# ============================================================================
# IterBot - Teste de restauracao (nao toca no banco de producao)
# ============================================================================
# Restaura um backup num Postgres TEMPORARIO (container descartavel, sem porta
# publicada) e confere que o banco voltou inteiro: migracoes do Django, tabelas
# principais e contagem de linhas comparada com o banco de producao.
#
# Uso: deployment/scripts/restore-test.sh [backup.sql.gz]
#      (sem argumento: usa o backup diario mais recente)
# Sai com 0 se tudo conferir, 1 caso contrario.
# ============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
DB_CONTAINER="${DB_CONTAINER:-iterbot_db}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:15-alpine}"
TEST_CONTAINER="iterbot_restore_test_$$"
# Tabelas que precisam existir e ter as mesmas linhas que a producao.
TABLES=(django_migrations users_userprofile courses_course courses_searchterm jobs_job jobs_company)

BACKUP_FILE="${1:-$(ls -1t "${BACKUP_DIR}"/daily/iterbot_db_*.sql.gz 2>/dev/null | head -1)}"
if [ -z "${BACKUP_FILE}" ] || [ ! -f "${BACKUP_FILE}" ]; then
    echo "Nenhum backup encontrado"
    exit 1
fi

cleanup() { docker rm -f "${TEST_CONTAINER}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "Backup: ${BACKUP_FILE} ($(stat -c%s "${BACKUP_FILE}") bytes)"
gzip -t "${BACKUP_FILE}"

echo "Subindo Postgres temporario (${POSTGRES_IMAGE})..."
docker run -d --name "${TEST_CONTAINER}" --memory 256m \
    -e POSTGRES_USER=restore -e POSTGRES_PASSWORD=restore -e POSTGRES_DB=restore \
    "${POSTGRES_IMAGE}" >/dev/null
for _ in $(seq 1 30); do
    docker exec "${TEST_CONTAINER}" pg_isready -U restore -d restore >/dev/null 2>&1 && break
    sleep 1
done
docker exec "${TEST_CONTAINER}" pg_isready -U restore -d restore >/dev/null

start=$(date +%s)
gunzip -c "${BACKUP_FILE}" \
    | docker exec -i "${TEST_CONTAINER}" psql -q -v ON_ERROR_STOP=1 -U restore -d restore >/dev/null
echo "Restaurado em $(( $(date +%s) - start ))s"

count() { # container user db table
    docker exec "$1" psql -U "$2" -d "$3" -tAc "SELECT count(*) FROM $4" 2>/dev/null || echo "ERRO"
}

compare_with_prod=0
if docker inspect "${DB_CONTAINER}" >/dev/null 2>&1; then
    compare_with_prod=1
    PROD_USER="$(docker exec "${DB_CONTAINER}" printenv POSTGRES_USER)"
    PROD_DB="$(docker exec "${DB_CONTAINER}" printenv POSTGRES_DB)"
fi

fail=0
printf "\n%-24s %10s %10s\n" "tabela" "backup" "producao"
for table in "${TABLES[@]}"; do
    restored="$(count "${TEST_CONTAINER}" restore restore "${table}")"
    prod="-"
    if [ "${compare_with_prod}" = 1 ]; then
        prod="$(count "${DB_CONTAINER}" "${PROD_USER}" "${PROD_DB}" "${table}")"
    fi
    status="OK"
    if [ "${restored}" = "ERRO" ]; then
        status="FALHOU (tabela ausente)"; fail=1
    elif [ "${table}" = "django_migrations" ] && [ "${restored}" -eq 0 ]; then
        status="FALHOU (sem migracoes)"; fail=1
    elif [ "${prod}" != "-" ] && [ "${prod}" != "${restored}" ]; then
        # o backup e de horas atras: diferenca e esperada se houve uso depois
        status="difere da producao (backup e anterior?)"
    fi
    printf "%-24s %10s %10s  %s\n" "${table}" "${restored}" "${prod}" "${status}"
done

if [ "${fail}" -ne 0 ]; then
    echo -e "\nTESTE DE RESTAURACAO FALHOU"
    exit 1
fi
echo -e "\nTESTE DE RESTAURACAO OK"
