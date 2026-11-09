#!/usr/bin/env bash
# ============================================================================
# IterBot - Rollback no host gosh (rodar NO HOST, dentro de ~/iterbot)
# ============================================================================
# Uso: deployment/scripts/rollback.sh [commit]   (padrao: o commit anterior, HEAD@{1})
#
# Volta o CODIGO para o commit indicado reaproveitando o deploy.sh (backup,
# rebuild, smoke-check). ATENCAO: migracoes NAO sao desfeitas. Se o deploy que
# esta sendo revertido trouxe migracao, restaure tambem o banco com o backup
# feito antes dele (o deploy.sh sempre faz um):
#   deployment/scripts/restore-postgres.sh backups/daily/iterbot_db_<antes-do-deploy>.sql.gz
# ============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../.."

TARGET="${1:-$(git rev-parse --short 'HEAD@{1}')}"
echo "Rollback: $(git rev-parse --short HEAD) -> ${TARGET}"
echo "Migracoes entre os dois commits (nao serao desfeitas):"
git diff --name-only "${TARGET}" HEAD -- 'apps/*/migrations/*.py' || true
read -r -p "Continuar? [s/N] " answer
[[ "${answer}" =~ ^[sS]$ ]] || { echo "Cancelado."; exit 0; }

exec bash "${SCRIPT_DIR}/deploy.sh" "${TARGET}"
