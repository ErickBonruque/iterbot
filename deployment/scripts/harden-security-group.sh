#!/bin/bash
# ============================================================================
# IterBot - Harden EC2 Security Group
# ============================================================================
# Removes public access to ports 3000, 8000, 8080 from the EC2 Security Group.
# Verifies only ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) remain open.
#
# Usage: ./deployment/scripts/harden-security-group.sh
#
# Prerequisites: AWS CLI configured with appropriate permissions
# ============================================================================
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ALLOWED_PORTS=(22 80 443)
BLOCKED_PORTS=(3000 8000 8080)

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  IterBot - Harden Security Group${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Auto-detect EC2 instance ID from metadata endpoint
echo -e "${BLUE}Detecting EC2 instance ID...${NC}"
INSTANCE_ID=$(curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || true)

if [ -z "$INSTANCE_ID" ]; then
    echo -e "${RED}ERROR: Could not detect instance ID from metadata endpoint.${NC}"
    echo -e "${YELLOW}Set INSTANCE_ID environment variable manually.${NC}"
    echo ""
    echo "Usage: INSTANCE_ID=i-xxxxx ./deployment/scripts/harden-security-group.sh"
    exit 1
fi

echo -e "${GREEN}Instance ID: ${INSTANCE_ID}${NC}"

# Get Security Group ID from instance
SG_ID=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || true)

if [ -z "$SG_ID" ]; then
    echo -e "${RED}ERROR: Could not determine Security Group ID.${NC}"
    echo -e "${YELLOW}Ensure AWS CLI is configured and the instance exists.${NC}"
    exit 1
fi

echo -e "${GREEN}Security Group ID: ${SG_ID}${NC}"
echo ""

# List current inbound rules
echo -e "${BLUE}Current inbound rules:${NC}"
aws ec2 describe-security-groups \
    --group-ids "$SG_ID" \
    --query 'SecurityGroups[0].IpPermissions' \
    --output table 2>/dev/null || true
echo ""

# Remove blocked ports
REMOVED=0
for PORT in "${BLOCKED_PORTS[@]}"; do
    echo -e "${BLUE}Checking port ${PORT}...${NC}"

    RULES=$(aws ec2 describe-security-groups \
        --group-ids "$SG_ID" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`${PORT}\`]" \
        --output json 2>/dev/null || echo "[]")

    RULE_COUNT=$(echo "$RULES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    if [ "$RULE_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}Removing port ${PORT} from Security Group...${NC}"

        PROTOCOL=$(echo "$RULES" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['IpProtocol'])" 2>/dev/null || echo "tcp")

        CIDRS=$(echo "$RULES" | python3 -c "
import sys, json
rules = json.load(sys.stdin)
for rule in rules:
    for rng in rule.get('IpRanges', []):
        print(rng['CidrIp'])
    for rng in rule.get('Ipv6Ranges', []):
        print(rng['CidrIpv6'])
" 2>/dev/null || true)

        for CIDR in $CIDRS; do
            aws ec2 revoke-security-group-ingress \
                --group-id "$SG_ID" \
                --protocol "$PROTOCOL" \
                --port "$PORT" \
                --cidr "$CIDR" 2>/dev/null && \
                echo -e "${GREEN}  Removed ${PROTOCOL}:${PORT} from ${CIDR}${NC}" || \
                echo -e "${YELLOW}  Could not remove ${PROTOCOL}:${PORT} from ${CIDR} (may not exist)${NC}"
        done
        REMOVED=$((REMOVED + 1))
    else
        echo -e "${GREEN}  Port ${PORT} is not open (already secure)${NC}"
    fi
done

echo ""

# Verify remaining rules
echo -e "${BLUE}Verifying remaining inbound rules...${NC}"
REMAINING=$(aws ec2 describe-security-groups \
    --group-ids "$SG_ID" \
    --query 'SecurityGroups[0].IpPermissions' \
    --output json 2>/dev/null || echo "[]")

UNEXPECTED=""
for PORT_INFO in $(echo "$REMAINING" | python3 -c "
import sys, json
perms = json.load(sys.stdin)
for p in perms:
    print(f\"{p.get('FromPort', 'all')}:{p.get('IpProtocol', '?')}\")
" 2>/dev/null); do
    PORT_NUM="${PORT_INFO%%:*}"
    if [[ ! " ${ALLOWED_PORTS[*]} " =~ " ${PORT_NUM} " ]]; then
        UNEXPECTED="${UNEXPECTED} ${PORT_NUM}"
    fi
done

echo -e "${BLUE}Remaining rules:${NC}"
aws ec2 describe-security-groups \
    --group-ids "$SG_ID" \
    --query 'SecurityGroups[0].IpPermissions' \
    --output table 2>/dev/null || true

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  Security Group Hardening Complete${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Removed ${REMOVED} port(s) from public access."
echo -e "Allowed ports: ${ALLOWED_PORTS[*]}"

if [ -n "$UNEXPECTED" ]; then
    echo -e "${RED}WARNING: Unexpected ports still open:${UNEXPECTED}${NC}"
    echo -e "${YELLOW}Review and remove manually if needed.${NC}"
    exit 1
else
    echo -e "${GREEN}Only expected ports (22, 80, 443) are open.${NC}"
    exit 0
fi