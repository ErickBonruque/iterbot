#!/usr/bin/env bash
# ============================================================================
# IterBot - Backup diario do PostgreSQL (host gosh)
# ============================================================================
# 1. pg_dump do container iterbot_db -> backups/daily/iterbot_db_AAAAMMDD_HHMMSS.sql.gz
#    (dump com --clean --if-exists: restaura por cima de um banco existente)
# 2. Copia da configuracao que NAO esta no git (.env, secrets/,
#    docker-compose.resources.yml) -> backups/daily/iterbot_config_*.tar.gz
#    (sem ENCRYPTION_KEY os campos criptografados do banco ficam ilegiveis)
# 3. Valida (tamanho, gzip -t e rodape "dump complete" do pg_dump)
# 4. Rotacao: BACKUP_KEEP_DAILY diarios (padrao 14); aos domingos copia para
#    backups/weekly/ e mantem BACKUP_KEEP_WEEKLY semanais (padrao 4)
# 5. Copia fora do host (opcional): se OFFSITE_REMOTE estiver definido (ex.:
#    "iterbot-offsite:" — remote rclone do tipo crypt sobre um bucket B2/R2),
#    envia os arquivos do dia e apaga la os mais velhos que OFFSITE_KEEP_DAYS.
# 6. Qualquer falha -> alerta por e-mail (manage.py send_ops_alert) e exit 1.
#
# Agendamento: deployment/scripts/install-backup-cron.sh (cron do usuario).
# Restauracao: restore-postgres.sh <arquivo>; teste: restore-test.sh.
#
# Variaveis (todas opcionais; podem vir do .env do projeto):
#   BACKUP_DIR, BACKUP_KEEP_DAILY, BACKUP_KEEP_WEEKLY, OFFSITE_REMOTE,
#   OFFSITE_KEEP_DAYS, DB_CONTAINER, BACKEND_CONTAINER
# ============================================================================
set -Eeuo pipefail
umask 077
# cron roda com PATH minimo; sem root o rclone fica em ~/bin ou ~/.local/bin.
export PATH="${HOME}/bin:${HOME}/.local/bin:/usr/local/bin:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

# Le so as chaves de backup do .env (sem "source": o .env tem segredos e
# valores que o bash interpretaria).
if [ -f "${PROJECT_DIR}/.env" ]; then
    while IFS='=' read -r key value; do
        if [ -z "${!key:-}" ]; then export "${key}=${value}"; fi
    done < <(grep -E '^(BACKUP_DIR|BACKUP_KEEP_DAILY|BACKUP_KEEP_WEEKLY|OFFSITE_REMOTE|OFFSITE_KEEP_DAYS)=' "${PROJECT_DIR}/.env" || true)
fi

BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-14}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-4}"
OFFSITE_REMOTE="${OFFSITE_REMOTE:-}"
OFFSITE_KEEP_DAYS="${OFFSITE_KEEP_DAYS:-30}"
DB_CONTAINER="${DB_CONTAINER:-iterbot_db}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-iterbot_backend}"
MIN_DUMP_BYTES=1000

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DAILY_DIR="${BACKUP_DIR}/daily"
WEEKLY_DIR="${BACKUP_DIR}/weekly"
DUMP_FILE="${DAILY_DIR}/iterbot_db_${TIMESTAMP}.sql.gz"
CONFIG_FILE="${DAILY_DIR}/iterbot_config_${TIMESTAMP}.tar.gz"
STEP="inicio"

log() { echo "[$(date -Iseconds)] $*"; }

alert() {
    local body="$1"
    if docker exec "${BACKEND_CONTAINER}" python manage.py send_ops_alert \
        --subject "Backup do banco FALHOU em $(hostname)" --body "${body}" >/dev/null 2>&1; then
        log "alerta enviado por e-mail"
    else
        log "AVISO: nao consegui enviar o alerta por e-mail"
    fi
}

on_error() {
    local code=$?
    rm -f "${DUMP_FILE}.partial" "${CONFIG_FILE}.partial"
    log "ERRO na etapa '${STEP}' (codigo ${code})"
    alert "Etapa: ${STEP}
Codigo de saida: ${code}
Host: $(hostname)
Data: $(date -Iseconds)
Log: ${BACKUP_DIR}/backup.log"
    exit 1
}
trap on_error ERR

prune() {
    # mantem os N mais novos de um padrao, apaga o resto
    local dir="$1" pattern="$2" keep="$3"
    find "${dir}" -maxdepth 1 -type f -name "${pattern}" -printf '%T@ %p\n' \
        | sort -rn | tail -n +"$((keep + 1))" | cut -d' ' -f2- \
        | while read -r old; do log "rotacao: removendo $(basename "${old}")"; rm -f "${old}"; done
}

mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}"

STEP="pg_dump"
DB_USER="$(docker exec "${DB_CONTAINER}" printenv POSTGRES_USER)"
DB_NAME="$(docker exec "${DB_CONTAINER}" printenv POSTGRES_DB)"
log "backup de ${DB_NAME} (${DB_CONTAINER}) -> ${DUMP_FILE}"
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" \
    --clean --if-exists --no-owner --no-privileges \
    | gzip -9 > "${DUMP_FILE}.partial"

STEP="validacao do dump"
size="$(stat -c%s "${DUMP_FILE}.partial")"
[ "${size}" -gt "${MIN_DUMP_BYTES}" ] || { log "dump pequeno demais (${size} bytes)"; false; }
gzip -t "${DUMP_FILE}.partial"
gunzip -c "${DUMP_FILE}.partial" | tail -n 5 | grep -q "PostgreSQL database dump complete" \
    || { log "dump sem o rodape 'dump complete' (truncado?)"; false; }
mv "${DUMP_FILE}.partial" "${DUMP_FILE}"
log "dump ok (${size} bytes)"

STEP="copia da configuracao"
config_items=()
for item in .env secrets docker-compose.resources.yml; do
    if [ -e "${PROJECT_DIR}/${item}" ]; then config_items+=("${item}"); fi
done
if [ "${#config_items[@]}" -gt 0 ]; then
    tar -czf "${CONFIG_FILE}.partial" -C "${PROJECT_DIR}" "${config_items[@]}"
    mv "${CONFIG_FILE}.partial" "${CONFIG_FILE}"
    log "configuracao ok (${config_items[*]})"
fi

STEP="rotacao"
if [ "$(date +%u)" = "7" ]; then
    cp -p "${DUMP_FILE}" "${WEEKLY_DIR}/"
    if [ -f "${CONFIG_FILE}" ]; then cp -p "${CONFIG_FILE}" "${WEEKLY_DIR}/"; fi
    log "copia semanal feita"
fi
prune "${DAILY_DIR}" 'iterbot_db_*.sql.gz' "${BACKUP_KEEP_DAILY}"
prune "${DAILY_DIR}" 'iterbot_config_*.tar.gz' "${BACKUP_KEEP_DAILY}"
prune "${WEEKLY_DIR}" 'iterbot_db_*.sql.gz' "${BACKUP_KEEP_WEEKLY}"
prune "${WEEKLY_DIR}" 'iterbot_config_*.tar.gz' "${BACKUP_KEEP_WEEKLY}"

if [ -n "${OFFSITE_REMOTE}" ]; then
    STEP="copia fora do host (rclone ${OFFSITE_REMOTE})"
    remote="${OFFSITE_REMOTE%/}"
    [[ "${remote}" == *: ]] || remote="${remote}/"
    rclone copy "${DUMP_FILE}" "${remote}daily" --no-traverse
    if [ -f "${CONFIG_FILE}" ]; then rclone copy "${CONFIG_FILE}" "${remote}daily" --no-traverse; fi
    rclone delete "${remote}daily" --min-age "${OFFSITE_KEEP_DAYS}d"
    log "copia fora do host ok (${remote}daily, retencao ${OFFSITE_KEEP_DAYS} dias)"
else
    log "OFFSITE_REMOTE vazio: sem copia fora do host"
fi

date -Iseconds > "${BACKUP_DIR}/last-success"
log "backup concluido"
