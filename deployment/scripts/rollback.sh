#!/bin/bash
# ============================================================================
# IterBot - Rollback Script
# ============================================================================
# Rolls back to a previous commit and rebuilds containers.
# Runs smoke check after rollback to verify health.
#
# Usage: ./deployment/scripts/rollback.sh [--commit HASH]
#   --commit  Specify commit hash to rollback to (default: HEAD^)
# ============================================================================
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/iterbot}"
ROLLBACK_COMMIT="${2:-HEAD^}"
DOMAIN="${DOMAIN:-localhost}"

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --commit)
            ROLLBACK_COMMIT="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--commit HASH]"
            exit 1
            ;;
    esac
done

# Default to HEAD^ if no commit specified
if [ "$ROLLBACK_COMMIT" = "HEAD^" ]; then
    ROLLBACK_COMMIT=$(git -C "$PROJECT_DIR" rev-parse HEAD^ 2>/dev/null || echo "HEAD^")
fi

echo "============================================"
echo "  IterBot - Rollback"
echo "============================================"
echo ""

cd "$PROJECT_DIR"

CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TARGET_COMMIT=$(git rev-parse --short "$ROLLBACK_COMMIT" 2>/dev/null || echo "$ROLLBACK_COMMIT")

echo "Current commit:  ${CURRENT_COMMIT}"
echo "Rollback target: ${TARGET_COMMIT}"
echo ""

# Fetch latest from origin
echo "Fetching from origin..."
git fetch origin

# Show recent commits for context
echo ""
echo "Recent commits:"
git log --oneline -5
echo ""

# Checkout rollback commit
echo "Checking out ${TARGET_COMMIT}..."
git checkout "$ROLLBACK_COMMIT"

# Rebuild containers
echo ""
echo "Rebuilding containers..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# Run smoke check
echo ""
echo "Running smoke check..."
DOMAIN_TO_CHECK="${DOMAIN}"
if [ "$DOMAIN_TO_CHECK" = "localhost" ]; then
    DOMAIN_TO_CHECK=$(git -C "$PROJECT_DIR" config --get deploy.domain 2>/dev/null || echo "localhost")
fi

if bash ./deployment/scripts/smoke-check.sh "$DOMAIN_TO_CHECK"; then
    echo ""
    echo "============================================"
    echo "  Rollback successful!"
    echo "  Now on commit: ${TARGET_COMMIT}"
    echo "============================================"
    exit 0
else
    echo ""
    echo "============================================"
    echo "  Rollback completed but smoke check FAILED!"
    echo "  Manual verification required."
    echo "============================================"
    exit 1
fi