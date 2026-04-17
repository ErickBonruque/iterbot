#!/bin/bash

# ============================================================================
# IterBot - Environment Validation Script
# ============================================================================
# This script validates that the environment is correctly configured before
# starting the application.
#
# Usage: ./deployment/scripts/validate_environment.sh [--ec2]
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

inc_error() {
    ERRORS=$((ERRORS + 1))
}

inc_warning() {
    WARNINGS=$((WARNINGS + 1))
}

# Detectar modo EC2
EC2_MODE=false
if [[ "${1:-}" == "--ec2" ]]; then
    EC2_MODE=true
fi

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔍 IterBot Environment Validation${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Function to check if command exists
check_command() {
    local cmd=$1
    local required=$2

    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✅ $cmd is installed${NC}"
        return 0
    fi

    if [ "$required" = "true" ]; then
        echo -e "${RED}❌ $cmd is NOT installed (required)${NC}"
        inc_error
    else
        echo -e "${YELLOW}⚠️  $cmd is NOT installed (optional)${NC}"
        inc_warning
    fi
    return 1
}

# Function to check file exists
check_file() {
    local file=$1
    local required=$2

    if [ -f "$file" ]; then
        local size
        size=$(wc -c < "$file")
        if [ "$size" -eq 0 ]; then
            echo -e "${RED}❌ $file exists but is EMPTY${NC}"
            inc_error
            return 1
        fi

        echo -e "${GREEN}✅ $file exists ($size bytes)${NC}"
        return 0
    fi

    if [ "$required" = "true" ]; then
        echo -e "${RED}❌ $file NOT found (required)${NC}"
        inc_error
    else
        echo -e "${YELLOW}⚠️  $file NOT found (optional)${NC}"
        inc_warning
    fi
    return 1
}

# Check required commands
echo -e "${BLUE}📦 Checking required commands...${NC}"
check_command "docker" true
check_command "git" true

# Checar docker compose plugin (sem hifen)
if docker compose version &>/dev/null; then
    echo -e "${GREEN}docker compose plugin disponivel${NC}"
else
    echo -e "${RED}docker compose plugin NAO encontrado (required)${NC}"
    inc_error
fi
echo ""

# Check optional commands
echo -e "${BLUE}📦 Checking optional commands...${NC}"
check_command "python3" false
check_command "openssl" false
if [ "$EC2_MODE" = true ]; then
    check_command "aws" true
    if command -v aws &> /dev/null; then
        if aws sts get-caller-identity &> /dev/null; then
            echo -e "${GREEN}IAM Role funcional${NC}"
        else
            echo -e "${RED}IAM Role NAO configurada (required para backup S3)${NC}"
            inc_error
        fi
    fi
else
    check_command "aws" false
fi
echo ""

# Check secrets directory
echo -e "${BLUE}📁 Checking secrets directory...${NC}"
if [ -d "./secrets" ]; then
    echo -e "${GREEN}✅ secrets/ directory exists${NC}"
else
    echo -e "${RED}❌ secrets/ directory NOT found${NC}"
    inc_error
fi
echo ""

# Check secret files
echo -e "${BLUE}🔐 Checking secret files...${NC}"
check_file "./secrets/django_secret_key.txt" true
check_file "./secrets/postgres_password.txt" true
check_file "./secrets/waha_api_key.txt" true
check_file "./secrets/waha_dashboard_password.txt" true
check_file "./secrets/waha_swagger_password.txt" true
if [ "$EC2_MODE" = true ]; then
    check_file "./secrets/email_password.txt" true
else
    check_file "./secrets/email_password.txt" false
fi
echo ""

# Check for invalid characters in secrets
echo -e "${BLUE}🔍 Validating secret content...${NC}"
for file in ./secrets/*.txt; do
    if [ -f "$file" ]; then
        if [ "$(wc -l < "$file")" -gt 1 ]; then
            echo -e "${YELLOW}⚠️  $(basename "$file") contains newline characters${NC}"
            inc_warning
        fi

        if grep -q $'\r' "$file"; then
            echo -e "${YELLOW}⚠️  $(basename "$file") contains carriage return characters${NC}"
            inc_warning
        fi

        content=$(cat "$file")
        trimmed=$(echo -n "$content" | tr -d ' \t\n\r')
        if [ "$content" != "$trimmed" ]; then
            echo -e "${YELLOW}⚠️  $(basename "$file") has leading/trailing whitespace${NC}"
            inc_warning
        fi
    fi
done

if [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}✅ All secrets are clean${NC}"
fi
echo ""

# Check .env file
echo -e "${BLUE}⚙️  Checking configuration files...${NC}"
if [ "$EC2_MODE" = true ]; then
    check_file ".env" true
else
    check_file ".env" false
fi
check_file ".env.production.example" true
check_file "docker-compose.yml" true
echo ""

# Check Docker
echo -e "${BLUE}🐳 Checking Docker status...${NC}"
if docker info &> /dev/null; then
    echo -e "${GREEN}✅ Docker is running${NC}"
else
    echo -e "${RED}❌ Docker is NOT running${NC}"
    inc_error
fi
echo ""

# Check docker-compose syntax
echo -e "${BLUE} Validating docker-compose.yml...${NC}"
if docker compose config > /dev/null 2>&1; then
    echo -e "${GREEN}docker-compose.yml is valid${NC}"
else
    echo -e "${RED}docker-compose.yml has syntax errors${NC}"
    inc_error
fi
echo ""

# Check entrypoint permissions
echo -e "${BLUE} Checking entrypoint permissions...${NC}"
if [ -f "docker/waha/entrypoint.sh" ]; then
    if [ -x "docker/waha/entrypoint.sh" ]; then
        echo -e "${GREEN}✅ docker/waha/entrypoint.sh is executable${NC}"
    else
        echo -e "${RED}❌ docker/waha/entrypoint.sh is NOT executable${NC}"
        echo -e "${YELLOW}   Run: chmod +x docker/waha/entrypoint.sh${NC}"
        inc_error
    fi
else
    echo -e "${RED}❌ docker/waha/entrypoint.sh NOT found${NC}"
    inc_error
fi
echo ""

# Summary
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}📊 Validation Summary${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}🎉 Perfect! No errors or warnings found.${NC}"
    echo -e "${GREEN}✅ Environment is ready to start!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo -e "  1. ${GREEN}docker compose up -d${NC}"
    echo -e "  2. ${GREEN}docker compose logs -f${NC}"
    exit 0
elif [ "$ERRORS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Found $WARNINGS warning(s)${NC}"
    echo -e "${GREEN}✅ Environment is OK to start, but consider fixing warnings.${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo -e "${RED}⛔ Please fix errors before starting!${NC}"
    echo ""
    echo -e "${BLUE}Common fixes:${NC}"
    echo -e "  • Run: ${GREEN}./deployment/scripts/setup_secrets.sh${NC}"
    echo -e "  • Run: ${GREEN}chmod +x docker/waha/entrypoint.sh${NC}"
    echo -e "  • Run: ${GREEN}cp .env.production.example .env${NC}"
    exit 1
fi
