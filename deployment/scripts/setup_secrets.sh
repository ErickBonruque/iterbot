#!/bin/bash

# ============================================================================
# CapyVagas - Secrets Setup Script
# ============================================================================
# This script generates secure random secrets for the application.
# It creates all necessary secret files with proper permissions.
#
# Usage: ./deployment/scripts/setup_secrets.sh
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SECRETS_DIR="./secrets"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔐 CapyVagas Secrets Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Verify secrets directory exists
if [ ! -d "$SECRETS_DIR" ]; then
    echo -e "${RED}❌ Error: Secrets directory not found!${NC}"
    echo -e "${YELLOW}Expected: $PROJECT_ROOT/$SECRETS_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}📁 Secrets directory: $SECRETS_DIR${NC}"
echo ""

# Function to generate secure random password
generate_password() {
    openssl rand -base64 32 | tr -d '\n\r' | tr -d ' '
}

# Function to generate Django secret key
generate_django_secret() {
    if command -v python3 &> /dev/null; then
        python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key(), end="")' 2>/dev/null || generate_password
    else
        generate_password
    fi
}

# Function to create secret file
create_secret() {
    local filename=$1
    local generator=$2
    local filepath="$SECRETS_DIR/$filename"
    
    if [ -f "$filepath" ]; then
        echo -e "${YELLOW}⏭️  $filename already exists, skipping...${NC}"
        # Verify it's not empty
        if [ ! -s "$filepath" ]; then
            echo -e "${RED}   ⚠️  WARNING: File exists but is empty!${NC}"
            read -p "   Regenerate? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                $generator > "$filepath"
                echo -e "${GREEN}   ✅ Regenerated${NC}"
            fi
        fi
    else
        echo -e "${BLUE}📝 Generating $filename...${NC}"
        $generator > "$filepath"
        chmod 600 "$filepath"
        echo -e "${GREEN}✅ $filename created${NC}"
    fi
}

# Generate all secrets
echo -e "${BLUE}Generating secrets...${NC}"
echo ""

create_secret "django_secret_key.txt" generate_django_secret
create_secret "postgres_password.txt" generate_password
create_secret "waha_api_key.txt" generate_password
create_secret "waha_dashboard_password.txt" generate_password
create_secret "waha_swagger_password.txt" generate_password

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ All secrets configured successfully!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Display summary
echo -e "${BLUE}📋 Summary:${NC}"
echo ""
for file in "$SECRETS_DIR"/*.txt; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        size=$(wc -c < "$file")
        echo -e "  ${GREEN}✓${NC} $filename (${size} bytes)"
    fi
done

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTES${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "1. ${YELLOW}NEVER${NC} commit these files to Git"
echo -e "2. Keep backups in a ${GREEN}secure location${NC}"
echo -e "3. Use ${GREEN}different secrets${NC} for each environment"
echo -e "4. ${YELLOW}Rotate secrets${NC} periodically"
echo ""

# Display credentials for WAHA
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}🔑 WAHA Dashboard Credentials${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "  URL:      ${GREEN}http://localhost:3000/dashboard${NC}"
echo -e "  Username: ${GREEN}admin${NC}"
echo -e "  Password: ${YELLOW}(stored in secrets/waha_dashboard_password.txt)${NC}"
echo ""
echo -e "To view your password:"
echo -e "  ${BLUE}cat secrets/waha_dashboard_password.txt${NC}"
echo ""

echo -e "${GREEN}🚀 Ready to start! Run: docker-compose up -d${NC}"
echo ""
