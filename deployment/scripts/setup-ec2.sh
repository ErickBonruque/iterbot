#!/bin/bash
# ============================================================================
# IterBot - Provisionamento EC2 (Ubuntu 22.04 LTS)
# ============================================================================
# Executa a configuracao inicial de uma instancia EC2 para rodar o IterBot.
#
# Uso: sudo ./deployment/scripts/setup-ec2.sh
# ============================================================================
set -euo pipefail

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

REPO_URL="${REPO_URL:-https://github.com/ErickBonruque/IterBot-UTFPR.git}"
PROJECT_DIR="/home/ubuntu/iterbot"
# Naming AWS padronizado (para identificacao em contas com multiplos projetos)
# EC2 Instance:   iterbot-utfpr-prod
# Security Group: iterbot-utfpr-sg
# Key Pair:       iterbot-utfpr-key
# S3 Bucket:      iterbot-utfpr-backups
# IAM Role (EC2): iterbot-utfpr-ec2-role

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  IterBot - Provisionamento EC2${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# 1. Atualizar pacotes do sistema
echo -e "${GREEN}[1/9] Atualizando pacotes do sistema...${NC}"
apt-get update -y
apt-get upgrade -y

# 2. Instalar dependencias
echo -e "${GREEN}[2/9] Instalando dependencias...${NC}"
apt-get install -y git curl unzip openssl jq

# 3. Instalar Docker Engine + Compose Plugin
echo -e "${GREEN}[3/9] Instalando Docker Engine + Compose Plugin...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
else
    echo "  Docker ja instalado, pulando..."
fi

# 4. Adicionar usuario ubuntu ao grupo docker
echo -e "${GREEN}[4/9] Configurando usuario ubuntu no grupo docker...${NC}"
usermod -aG docker ubuntu

# 5. Instalar AWS CLI v2
echo -e "${GREEN}[5/9] Instalando AWS CLI v2...${NC}"
if ! command -v /usr/local/bin/aws &> /dev/null; then
    cd /tmp
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
    cd -
else
    echo "  AWS CLI ja instalado, pulando..."
fi

# 6. Configurar log rotation do Docker
echo -e "${GREEN}[6/9] Configurando Docker log rotation...${NC}"
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# 7. Reiniciar Docker
echo -e "${GREEN}[7/9] Reiniciando Docker...${NC}"
systemctl restart docker

# 8. Clonar repositorio
echo -e "${GREEN}[8/9] Clonando repositorio...${NC}"
if [ ! -d "${PROJECT_DIR}" ]; then
    git clone "${REPO_URL}" "${PROJECT_DIR}"
    chown -R ubuntu:ubuntu "${PROJECT_DIR}"
else
    echo "  Repositorio ja existe em ${PROJECT_DIR}, pulando..."
fi

# 9. Configurar crontab para backup semanal (domingo 02:00)
echo -e "${GREEN}[9/9] Configurando crontab para backup semanal...${NC}"
CRON_CMD="0 2 * * 0 /bin/bash ${PROJECT_DIR}/deployment/scripts/backup-postgres.sh >> /var/log/iterbot-backup.log 2>&1"
(crontab -u ubuntu -l 2>/dev/null | grep -v "backup-postgres.sh" || true; echo "${CRON_CMD}") | crontab -u ubuntu -

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  Provisionamento concluido!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Proximos passos:"
echo "  1. Faca logout e login novamente (para aplicar grupo docker)"
echo "  2. cd ${PROJECT_DIR}"
echo "  3. cp .env.production.example .env"
echo "  4. Edite .env com seus valores reais (DOMAIN, senhas, etc)"
echo "  5. bash ./deployment/scripts/setup_secrets.sh"
echo "  6. bash ./deployment/scripts/validate_environment.sh --ec2"
echo "  7. docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d"
echo "  8. bash ./deployment/scripts/smoke-check.sh SEU-IP.sslip.io"
echo ""
