#!/usr/bin/env bash
# ec2_deploy.sh — Executado via AWS SSM no EC2 (user ubuntu).
# Mantem a logica de deploy versionada no repo para evitar escape hell no YAML.
#
# Variaveis esperadas:
#   BREVO_API_KEY_B64  (opcional) — chave Brevo codificada em base64.
#                                    Se vazia, secrets/brevo_api_key.txt nao e sobrescrito.
#
# Pre-requisitos no EC2:
#   - /home/ubuntu/iterbot clonado
#   - Docker + Docker Compose v2 instalados
#   - Secrets AWS ja presentes em /home/ubuntu/iterbot/.env

set -euo pipefail

REPO_DIR="/home/ubuntu/iterbot"
cd "$REPO_DIR"

# O git fetch/reset e feito pelo comando SSM antes de chamar este script
# (necessario porque na primeira execucao pos-merge este proprio arquivo
# precisa estar presente no HEAD da master).

echo "[deploy] garantindo estrutura de secrets/users"
mkdir -p secrets/users
if [ ! -f secrets/users/admin-users.txt ] || [ ! -f secrets/users/waha-users.txt ]; then
  set -a
  . ./.env
  set +a
  bash ./deployment/scripts/setup-htpasswd.sh
fi

echo "[deploy] normalizando .env via update_env_production.sh"
bash ./deployment/scripts/update_env_production.sh

set -a
. ./.env
set +a

mkdir -p secrets
echo "[deploy] escrevendo secrets AWS"
printf %s "${AWS_ACCESS_KEY_ID:-}" > secrets/aws_access_key_id.txt
printf %s "${AWS_SECRET_ACCESS_KEY:-}" > secrets/aws_secret_access_key.txt
chmod 600 secrets/aws_access_key_id.txt secrets/aws_secret_access_key.txt

if [ -n "${BREVO_API_KEY_B64:-}" ]; then
  echo "[deploy] atualizando secrets/brevo_api_key.txt a partir do GH secret"
  printf %s "${BREVO_API_KEY_B64}" | base64 -d > secrets/brevo_api_key.txt
  chmod 600 secrets/brevo_api_key.txt
else
  echo "[deploy] BREVO_API_KEY_B64 vazio — preservando secrets/brevo_api_key.txt existente"
fi

echo "[deploy] docker compose up"
docker container prune -f
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d --remove-orphans
docker image prune -f

echo "[deploy] smoke-check"
bash ./deployment/scripts/smoke-check.sh

echo "[deploy] concluido em $(date -Iseconds)"
