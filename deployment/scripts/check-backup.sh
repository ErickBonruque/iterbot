#!/bin/bash
# ============================================================================
# IterBot - Backup Check Script
# ============================================================================
# Verifies that a daily backup exists in S3 and sends alerts via AWS SES
# if the backup is missing or suspicious.
#
# Usage: ./deployment/scripts/check-backup.sh [--quiet]
#
# Environment variables:
#   S3_BACKUP_BUCKET  - S3 bucket name (default: iterbot-utfpr-backups)
#   S3_BACKUP_PREFIX  - S3 prefix (default: daily)
#   SENDER_EMAIL      - Sender email for alerts (default: bonruque@alunos.utfpr.edu.br)
#   ALERT_EMAIL       - Alert recipient email (default: same as SENDER_EMAIL)
# ============================================================================
set -euo pipefail

S3_BUCKET="${S3_BACKUP_BUCKET:-iterbot-utfpr-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-daily}"
SENDER_EMAIL="${SENDER_EMAIL:-bonruque@alunos.utfpr.edu.br}"
ALERT_EMAIL="${ALERT_EMAIL:-bonruque@alunos.utfpr.edu.br}"
QUIET="${QUIET:-false}"
AWS_BIN=$(command -v aws || echo "/usr/local/bin/aws")

if [ "${1:-}" = "--quiet" ]; then
    QUIET="true"
fi

TODAY=$(date +%Y%m%d)
HOSTNAME_STR=$(hostname 2>/dev/null || echo "unknown")

echo "[$(date -Iseconds)] Checking backup for ${TODAY}..."

# Check for today's backup in S3
BACKUP_LIST=$(${AWS_BIN} s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" 2>/dev/null | grep "${TODAY}" || echo "")

if [ -z "$BACKUP_LIST" ]; then
    echo "[ALERT] No backup found for today (${TODAY}) in s3://${S3_BUCKET}/${S3_PREFIX}/"

    ${AWS_BIN} ses send-email \
        --from "${SENDER_EMAIL}" \
        --to "${ALERT_EMAIL}" \
        --subject "[IterBot ALERT] Backup Check Failed - $(date +%Y-%m-%d)" \
        --text "Backup verification FAILED on ${HOSTNAME_STR}.

Date: $(date +%Y-%m-%d)
Bucket: s3://${S3_BUCKET}
Prefix: ${S3_PREFIX}/${TODAY}
Expected: At least one backup file for today
Found: No backup files

Action required: Check backup-postgres.sh logs and S3 bucket." \
        2>/dev/null || echo "[WARNING] Failed to send SES alert email"

    exit 1
fi

# Check backup file size
BACKUP_FILE=$(echo "$BACKUP_LIST" | sort | tail -1)
BACKUP_SIZE=$(echo "$BACKUP_FILE" | awk '{print $3}')

if [ -z "$BACKUP_SIZE" ] || [ "$BACKUP_SIZE" -lt 1000 ] 2>/dev/null; then
    echo "[ALERT] Backup file exists but may be corrupt (size: ${BACKUP_SIZE:-unknown})"

    ${AWS_BIN} ses send-email \
        --from "${SENDER_EMAIL}" \
        --to "${ALERT_EMAIL}" \
        --subject "[IterBot ALERT] Backup Check Failed - $(date +%Y-%m-%d)" \
        --text "Backup verification FAILED on ${HOSTNAME_STR}.

Date: $(date +%Y-%m-%d)
Bucket: s3://${S3_BUCKET}
File: ${BACKUP_FILE}
Size: ${BACKUP_SIZE:-unknown} bytes (expected > 1000)

Action required: Run restore-test.sh to verify backup integrity." \
        2>/dev/null || echo "[WARNING] Failed to send SES alert email"

    exit 1
fi

echo "[OK] Backup found: ${BACKUP_FILE} (${BACKUP_SIZE} bytes)"

if [ "$QUIET" != "true" ]; then
    ${AWS_BIN} ses send-email \
        --from "${SENDER_EMAIL}" \
        --to "${ALERT_EMAIL}" \
        --subject "[IterBot OK] Backup Check Passed - $(date +%Y-%m-%d)" \
        --text "Backup verification PASSED on ${HOSTNAME_STR}.

Date: $(date +%Y-%m-%d)
Bucket: s3://${S3_BUCKET}
File: ${BACKUP_FILE}
Size: ${BACKUP_SIZE} bytes

No action required." \
        2>/dev/null || echo "[WARNING] Failed to send SES success email"
fi

exit 0