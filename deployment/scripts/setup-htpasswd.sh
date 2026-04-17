#!/bin/bash
# ============================================================================
# IterBot - htpasswd Setup Script
# ============================================================================
# Generates BasicAuth user files for Traefik (WAHA Dashboard and Django Admin).
#
# Usage: ./deployment/scripts/setup-htpasswd.sh
#
# Environment variables:
#   WAHA_DASHBOARD_USERNAME  - WAHA dashboard username (default: admin)
#   WAHA_DASHBOARD_PASSWORD  - WAHA dashboard password (required if not interactive)
#   DJANGO_ADMIN_USERNAME     - Django Admin/Portal username (default: admin)
#   DJANGO_ADMIN_PASSWORD     - Django Admin/Portal password (required if not interactive)
# ============================================================================
set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
USERS_DIR="$PROJECT_ROOT/secrets/users"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  IterBot - htpasswd Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

mkdir -p "$USERS_DIR"

generate_hash() {
    local password="$1"
    local username="$2"
    if command -v htpasswd &>/dev/null; then
        htpasswd -nbB "$username" "$password"
    elif command -v python3 &>/dev/null; then
        python3 -c '
import bcrypt, sys
password = sys.argv[1].encode()
username = sys.argv[2]
hashed = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
print(f"{username}:{hashed.decode()}")
' "$password" "$username"
    else
        echo "ERROR: Neither htpasswd nor python3 with bcrypt available" >&2
        exit 1
    fi
}

# WAHA Dashboard
WAHA_USER="${WAHA_DASHBOARD_USERNAME:-admin}"
if [ -n "${WAHA_DASHBOARD_PASSWORD:-}" ]; then
    WAHA_PASS="$WAHA_DASHBOARD_PASSWORD"
else
    echo -e "${YELLOW}Enter WAHA Dashboard password for user '$WAHA_USER':${NC}"
    read -rs WAHA_PASS
    echo ""
fi

echo -e "${BLUE}Generating waha-users.txt...${NC}"
generate_hash "$WAHA_PASS" "$WAHA_USER" > "$USERS_DIR/waha-users.txt"
chmod 600 "$USERS_DIR/waha-users.txt"
echo -e "${GREEN}Created $USERS_DIR/waha-users.txt${NC}"

# Django Admin/Portal
ADMIN_USER="${DJANGO_ADMIN_USERNAME:-admin}"
if [ -n "${DJANGO_ADMIN_PASSWORD:-}" ]; then
    ADMIN_PASS="$DJANGO_ADMIN_PASSWORD"
else
    echo -e "${YELLOW}Enter Django Admin/Portal password for user '$ADMIN_USER':${NC}"
    read -rs ADMIN_PASS
    echo ""
fi

echo -e "${BLUE}Generating admin-users.txt...${NC}"
generate_hash "$ADMIN_PASS" "$ADMIN_USER" > "$USERS_DIR/admin-users.txt"
chmod 600 "$USERS_DIR/admin-users.txt"
echo -e "${GREEN}Created $USERS_DIR/admin-users.txt${NC}"

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  htpasswd files created successfully!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Files created:"
echo "  $USERS_DIR/waha-users.txt (WAHA Dashboard BasicAuth)"
echo "  $USERS_DIR/admin-users.txt (Django Admin/Portal BasicAuth)"
echo ""
echo "Permissions: 600 (owner read/write only)"