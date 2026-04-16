#!/bin/bash
# configure-branch-protection.sh
# Optional script to configure branch protection rules via GitHub CLI
# Note: Manual configuration via GitHub UI is recommended for most cases

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Branch Protection Configuration Script${NC}"
echo "=============================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed.${NC}"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub.${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
if [ -z "$REPO" ]; then
    echo -e "${RED}Error: Could not determine repository.${NC}"
    exit 1
fi

echo "Configuring branch protection for: $REPO"
echo ""

# Branch name pattern (default: master)
BRANCH_PATTERN="${1:-master}"

echo -e "${YELLOW}Note: This script is optional.${NC}"
echo "Manual configuration via GitHub UI is recommended for most cases."
echo ""
read -p "Continue with script-based configuration? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. Configure manually via:"
    echo "  Repository → Settings → Branches → Add rule"
    exit 0
fi

echo -e "${GREEN}Configuring branch protection rules...${NC}"

# Configure branch protection via GitHub API
gh api repos/"$REPO"/branches/"$BRANCH_PATTERN"/protection \
  --method PUT \
  --field required_status_checks='{"strict":false,"contexts":["Lint","Test","Security"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_last_push_approval":false}' \
  --field required_conversation_resolution=false \
  --field allow_force_pushes=false \
  --field allow_deletions=false \
  --field block_creations=false \
  --field require_signed_commits=false \
  --field require_linear_history=true \
  --field required_deployments=[] \
  --field restrictions=null 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Branch protection configured successfully!${NC}"
else
    echo -e "${YELLOW}⚠ Could not apply via API. You may need to configure manually.${NC}"
    echo ""
    echo "Manual configuration steps:"
    echo "  1. Go to Repository → Settings → Branches"
    echo "  2. Click 'Add rule'"
    echo "  3. Enter branch pattern: $BRANCH_PATTERN"
    echo "  4. Enable: Require a pull request before merging"
    echo "  5. Enable: Require approvals (1)"
    echo "  6. Enable: Dismiss stale pull request approvals"
    echo "  7. Enable: Require status checks to pass (Lint, Test, Security)"
    echo "  8. Enable: Require linear history"
fi

echo ""
echo -e "${YELLOW}Status checks configured:${NC}"
echo "  - Lint (ruff check + format)"
echo "  - Test (pytest with coverage)"
echo "  - Security (pip-audit + trivy)"
echo ""
echo -e "${GREEN}Done!${NC}"
