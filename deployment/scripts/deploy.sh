#!/usr/bin/env bash
# ============================================================================
# IterBot - Deploy no host gosh (rodar NO HOST, dentro de ~/iterbot)
# ============================================================================
# SSH do gosh so funciona da rede da UTFPR/VPN. Uso:
#   deployment/scripts/deploy.sh            # atualiza para origin/master
#   deployment/scripts/deploy.sh <commit>   # vai para um commit especifico (rollback)
#
# Etapas: checagens -> backup do banco -> git -> rebuild de backend/worker/beat
# (o start.sh do backend roda migrate + collectstatic) -> confere migracoes ->
# smoke-check -> limpa build cache e imagens orfas (o disco de 19 GB e o gargalo).
# Para no primeiro erro. O WAHA, o banco e o Redis NAO sao recriados.
# ============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_DIR}"

TARGET="${1:-}"
DOMAIN="${DOMAIN:-$(grep -E '^DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)}"
DOMAIN="${DOMAIN:-gosh.sh.utfpr.edu.br}"
APP_SERVICES=(backend celery_worker celery_beat)
MIN_FREE_MB=1500

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
# Limites de memoria do host (arquivo so existe no host, nao versionado).
if [ -f docker-compose.resources.yml ]; then COMPOSE+=(-f docker-compose.resources.yml); fi

log() { echo -e "\n[$(date +%H:%M:%S)] $*"; }
free_mb() { df -Pm / | awk 'NR==2 {print $4}'; }

log "1/7 checagens"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Ha alteracoes locais em arquivos versionados — resolva antes do deploy:"
    git status --short --untracked-files=no
    exit 1
fi
if [ ! -f docker-compose.resources.yml ]; then
    echo "AVISO: docker-compose.resources.yml ausente (sem limites de memoria)"
fi
echo "commit atual: $(git rev-parse --short HEAD) | disco livre: $(free_mb) MB"
if [ "$(free_mb)" -lt "${MIN_FREE_MB}" ]; then
    log "pouco disco antes do build — limpando build cache primeiro"
    docker builder prune -f >/dev/null
    echo "disco livre agora: $(free_mb) MB"
fi

log "2/7 backup do banco antes de mexer"
bash "${SCRIPT_DIR}/backup-postgres.sh"

log "3/7 git"
PREVIOUS="$(git rev-parse --short HEAD)"
git fetch --quiet origin
if [ -z "${TARGET}" ]; then
    git checkout --quiet master
    git merge --ff-only origin/master
else
    git checkout --quiet --detach "${TARGET}"
fi
CURRENT="$(git rev-parse --short HEAD)"
echo "${PREVIOUS} -> ${CURRENT}"
git log --oneline "${PREVIOUS}..${CURRENT}" 2>/dev/null | head -20 || true

log "4/7 rebuild e restart de ${APP_SERVICES[*]}"
"${COMPOSE[@]}" up -d --build "${APP_SERVICES[@]}"

log "5/7 aguardando o backend (migrate roda no start)"
for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' iterbot_backend 2>/dev/null || echo unknown)"
    if [ "${status}" = "healthy" ]; then break; fi
    sleep 5
done
echo "backend: ${status}"
if [ "${status}" != "healthy" ]; then
    docker logs --tail 40 iterbot_backend
    exit 1
fi
if docker exec iterbot_backend python manage.py migrate --check >/dev/null; then
    echo "migracoes: todas aplicadas"
else
    echo "HA MIGRACOES PENDENTES"
    exit 1
fi

log "6/7 smoke-check"
bash "${SCRIPT_DIR}/smoke-check.sh" "${DOMAIN}"

log "7/7 limpeza de disco"
docker builder prune -f >/dev/null
docker image prune -f >/dev/null
df -h /

log "deploy concluido: ${CURRENT}"
