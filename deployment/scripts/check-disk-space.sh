#!/bin/bash
# ============================================================================
# IterBot - Disk Space Check Script
# ============================================================================
# Monitors disk usage and sends alerts via AWS SES when usage exceeds
# a configurable threshold.
#
# Usage: ./deployment/scripts/check-disk-space.sh
#
# Environment variables:
#   DISK_THRESHOLD  - Usage percentage threshold (default: 80)
#   SENDER_EMAIL    - Sender email for alerts (default: bonruque@alunos.utfpr.edu.br)
#   ALERT_EMAIL     - Alert recipient email (default: same as SENDER_EMAIL)
# ============================================================================
set -euo pipefail

DISK_THRESHOLD="${DISK_THRESHOLD:-80}"
SENDER_EMAIL="${SENDER_EMAIL:-bonruque@alunos.utfpr.edu.br}"
ALERT_EMAIL="${ALERT_EMAIL:-bonruque@alunos.utfpr.edu.br}"
AWS_BIN=$(command -v aws || echo "/usr/local/bin/aws")
HOSTNAME_STR=$(hostname 2>/dev/null || echo "unknown")

# Get disk usage percentage for root partition
USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')

echo "[$(date -Iseconds)] Disk usage: ${USAGE}% (threshold: ${DISK_THRESHOLD}%)"

if [ "$USAGE" -ge "$DISK_THRESHOLD" ]; then
    echo "[ALERT] Disk usage ${USAGE}% exceeds threshold ${DISK_THRESHOLD}%"

    DISK_INFO=$(df -h 2>/dev/null || echo "df command failed")
    DOCKER_INFO=$(command -v docker &>/dev/null && docker system df 2>/dev/null || echo "Docker not available")

    ${AWS_BIN} ses send-email \
        --from "${SENDER_EMAIL}" \
        --to "${ALERT_EMAIL}" \
        --subject "[IterBot ALERT] Disk Space ${USAGE}% - $(date +%Y-%m-%d)" \
        --text "Disk usage on ${HOSTNAME_STR} is at ${USAGE}% (threshold: ${DISK_THRESHOLD}%).

Date: $(date +%Y-%m-%d)
Host: ${HOSTNAME_STR}

=== Disk Usage ===
${DISK_INFO}

=== Docker Disk Usage ===
${DOCKER_INFO}

Action required: Clean up disk space or increase storage capacity." \
        2>/dev/null || echo "[WARNING] Failed to send SES alert email"

    exit 1
fi

echo "[OK] Disk usage ${USAGE}% is below threshold ${DISK_THRESHOLD}%"
exit 0