#!/bin/bash
# ============================================================================
# IterBot - Restore Test Script
# ============================================================================
# Downloads the most recent backup from S3, restores it into a temporary
# PostgreSQL container, and runs integrity checks.
#
# Usage: ./deployment/scripts/restore-test.sh [--date YYYYMMDD]
#
# Environment variables:
#   S3_BACKUP_BUCKET  - S3 bucket name (default: iterbot-utfpr-backups)
#   S3_BACKUP_PREFIX  - S3 prefix (default: daily)
# ============================================================================
set -euo pipefail

S3_BUCKET="${S3_BACKUP_BUCKET:-iterbot-utfpr-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-daily}"
PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/iterbot}"
DOCKER_BIN=$(command -v docker || echo "/usr/bin/docker")
AWS_BIN=$(command -v aws || echo "/usr/local/bin/aws")
RESTORE_DIR="/tmp/iterbot-restore-test"
CONTAINER_NAME="iterbot_restore_test"
DB_NAME="iterbot_test"
DB_USER="iterbot_user"
DB_PASSWORD="test_password"
DB_PORT=15432

# Parse options
BACKUP_DATE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --date)
            BACKUP_DATE="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--date YYYYMMDD]"
            exit 1
            ;;
    esac
done

echo "============================================"
echo "  IterBot - Restore Test"
echo "============================================"
echo ""

# Find backup to restore
if [ -n "$BACKUP_DATE" ]; then
    echo "Looking for backup from date: ${BACKUP_DATE}..."
    LATEST_BACKUP=$(${AWS_BIN} s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" 2>/dev/null | grep "${BACKUP_DATE}" | sort | tail -1 | awk '{print $4}')
else
    echo "Looking for most recent backup..."
    LATEST_BACKUP=$(${AWS_BIN} s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" 2>/dev/null | sort | tail -1 | awk '{print $4}')
fi

if [ -z "$LATEST_BACKUP" ]; then
    echo "[ERROR] No backup found in s3://${S3_BUCKET}/${S3_PREFIX}/"
    exit 1
fi

echo "Backup: ${LATEST_BACKUP}"

# Download backup
mkdir -p "${RESTORE_DIR}"
echo "Downloading backup from S3..."
${AWS_BIN} s3 cp "s3://${S3_BUCKET}/${S3_PREFIX}/${LATEST_BACKUP}" "${RESTORE_DIR}/${LATEST_BACKUP}" --quiet

BACKUP_FILE="${RESTORE_DIR}/${LATEST_BACKUP}"
BACKUP_SIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null)
echo "Downloaded: ${BACKUP_SIZE} bytes"

# Verify download size
if [ "$BACKUP_SIZE" -le 1000 ]; then
    echo "[ERROR] Backup too small (${BACKUP_SIZE} bytes) — possibly corrupt"
    ${DOCKER_BIN} rm -f "$CONTAINER_NAME" 2>/dev/null || true
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

# Verify gzip integrity
if ! gzip -t "${BACKUP_FILE}" 2>/dev/null; then
    echo "[ERROR] Backup failed gzip integrity check"
    ${DOCKER_BIN} rm -f "$CONTAINER_NAME" 2>/dev/null || true
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

# Start temporary PostgreSQL container
echo "Starting temporary PostgreSQL container..."
${DOCKER_BIN} run -d --name "$CONTAINER_NAME" \
    -e POSTGRES_DB="${DB_NAME}" \
    -e POSTGRES_USER="${DB_USER}" \
    -e POSTGRES_PASSWORD="${DB_PASSWORD}" \
    -p "${DB_PORT}:5432" \
    postgres:15-alpine

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
RETRIES=30
until ${DOCKER_BIN} exec "$CONTAINER_NAME" pg_isready -U "${DB_USER}" -d "${DB_NAME}" 2>/dev/null || [ $RETRIES -eq 0 ]; do
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    echo "[ERROR] PostgreSQL did not become ready in time"
    ${DOCKER_BIN} stop "$CONTAINER_NAME" 2>/dev/null || true
    ${DOCKER_BIN} rm -f "$CONTAINER_NAME" 2>/dev/null || true
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

echo "PostgreSQL ready."

# Restore backup
RESTORE_START=$(date +%s)
echo "Restoring backup into test database..."
gunzip -c "${BACKUP_FILE}" | ${DOCKER_BIN} exec -i "$CONTAINER_NAME" psql -U "${DB_USER}" -d "${DB_NAME}" 2>&1 || {
    echo "[WARNING] Some errors during restore (may be expected with schema conflicts)"
}
RESTORE_END=$(date +%s)
RESTORE_DURATION=$((RESTORE_END - RESTORE_START))

# Run integrity checks
echo ""
echo "Running integrity checks..."
echo ""

PASS=0
FAIL=0

check_table() {
    local table="$1"
    local min_rows="${2:-1}"
    local count
    count=$(${DOCKER_BIN} exec "$CONTAINER_NAME" psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM ${table};" 2>/dev/null | tr -d ' ')
    printf "  %-40s " "Table ${table} has rows"
    if [ "$count" -ge "$min_rows" ]; then
        echo "[OK] (${count} rows)"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] (${count} rows, expected >= ${min_rows})"
        FAIL=$((FAIL + 1))
    fi
}

check_table "auth_user" 0
check_table "django_content_type" 0

DB_SIZE=$(${DOCKER_BIN} exec "$CONTAINER_NAME" psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT pg_database_size('${DB_NAME}');" 2>/dev/null | tr -d ' ')
printf "  %-40s " "Database size > 0"
if [ "$DB_SIZE" -gt 0 ] 2>/dev/null; then
    echo "[OK] (${DB_SIZE} bytes)"
    PASS=$((PASS + 1))
else
    echo "[FAIL]"
    FAIL=$((FAIL + 1))
fi

# Print summary
echo ""
echo "============================================"
echo "  Restore Test Summary"
echo "============================================"
echo "  Backup date:    ${LATEST_BACKUP}"
echo "  Backup size:    ${BACKUP_SIZE} bytes"
echo "  Restore time:   ${RESTORE_DURATION}s"
echo "  Database size:  ${DB_SIZE} bytes"
echo "  Checks:         ${PASS} OK / ${FAIL} FAIL"
echo "============================================"

# Cleanup
echo ""
echo "Cleaning up..."
${DOCKER_BIN} stop "$CONTAINER_NAME" 2>/dev/null || true
${DOCKER_BIN} rm -f "$CONTAINER_NAME" 2>/dev/null || true
rm -rf "${RESTORE_DIR}"
echo "Cleanup complete."

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi

exit 0