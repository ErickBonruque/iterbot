# ============================================================================
# CapyVagas-UTFPR Makefile
# ============================================================================
# Simplified commands for common operations
#
# Usage: make <command>
# Example: make setup
# ============================================================================

.PHONY: help setup validate start stop restart logs logs-waha logs-backend status clean rebuild test migrate makemigrations createsuperuser shell

# Default target
.DEFAULT_GOAL := help

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

## help: Show this help message
help:
	@echo "$(BLUE)============================================$(NC)"
	@echo "$(BLUE)CapyVagas-UTFPR - Available Commands$(NC)"
	@echo "$(BLUE)============================================$(NC)"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  $(GREEN)/' | sed 's/:/$(NC):/'
	@echo ""

## setup: Initial setup (secrets + validation)
setup:
	@echo "$(BLUE)🔧 Setting up CapyVagas...$(NC)"
	@./deployment/scripts/setup_secrets.sh
	@./deployment/scripts/validate_environment.sh

## validate: Validate environment configuration
validate:
	@./deployment/scripts/validate_environment.sh

## start: Start all services
start:
	@echo "$(BLUE)🚀 Starting CapyVagas...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)✅ Services started!$(NC)"
	@echo ""
	@make status

## stop: Stop all services
stop:
	@echo "$(BLUE)🛑 Stopping CapyVagas...$(NC)"
	@docker-compose stop
	@echo "$(GREEN)✅ Services stopped!$(NC)"

## restart: Restart all services
restart:
	@echo "$(BLUE)🔄 Restarting CapyVagas...$(NC)"
	@docker-compose restart
	@echo "$(GREEN)✅ Services restarted!$(NC)"

## logs: Show logs from all services
logs:
	@docker-compose logs -f

## logs-waha: Show logs from WAHA service
logs-waha:
	@docker-compose logs -f waha

## logs-backend: Show logs from backend service
logs-backend:
	@docker-compose logs -f backend

## status: Show status of all services
status:
	@echo "$(BLUE)📊 Service Status:$(NC)"
	@docker-compose ps
	@echo ""
	@echo "$(BLUE)🔗 Access URLs:$(NC)"
	@echo "  $(GREEN)WAHA Dashboard:$(NC)  http://localhost:3000/dashboard"
	@echo "  $(GREEN)Backend Dashboard:$(NC) http://localhost:8000/dashboard/"
	@echo "  $(GREEN)Django Admin:$(NC)     http://localhost:8000/admin/"
	@echo "  $(GREEN)API Docs:$(NC)         http://localhost:8000/api/docs/"
	@echo "  $(GREEN)Traefik:$(NC)          http://localhost:8080"

## clean: Stop and remove all containers, volumes
clean:
	@echo "$(YELLOW)⚠️  This will remove all containers and volumes!$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@docker-compose down -v
	@echo "$(GREEN)✅ Cleaned!$(NC)"

## rebuild: Rebuild and restart all services
rebuild:
	@echo "$(BLUE)🔨 Rebuilding CapyVagas...$(NC)"
	@docker-compose down
	@docker-compose build --no-cache
	@docker-compose up -d
	@echo "$(GREEN)✅ Rebuilt and started!$(NC)"

## test: Run tests
test:
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	@docker-compose exec backend pytest
	@echo "$(GREEN)✅ Tests completed!$(NC)"

## migrate: Run database migrations
migrate:
	@echo "$(BLUE)📦 Running migrations...$(NC)"
	@docker-compose exec backend python manage.py migrate
	@echo "$(GREEN)✅ Migrations completed!$(NC)"

## makemigrations: Create new migrations
makemigrations:
	@echo "$(BLUE)📝 Creating migrations...$(NC)"
	@docker-compose exec backend python manage.py makemigrations
	@echo "$(GREEN)✅ Migrations created!$(NC)"

## createsuperuser: Create Django superuser
createsuperuser:
	@echo "$(BLUE)👤 Creating superuser...$(NC)"
	@docker-compose exec backend python manage.py createsuperuser

## shell: Open Django shell
shell:
	@docker-compose exec backend python manage.py shell

## waha-restart: Restart only WAHA service
waha-restart:
	@echo "$(BLUE)🔄 Restarting WAHA...$(NC)"
	@docker-compose stop waha
	@docker-compose rm -f waha
	@docker-compose up -d waha
	@echo "$(GREEN)✅ WAHA restarted!$(NC)"
	@echo ""
	@echo "$(BLUE)📋 WAHA Credentials:$(NC)"
	@echo "  URL:      $(GREEN)http://localhost:3000/dashboard$(NC)"
	@echo "  Username: $(GREEN)admin$(NC)"
	@echo "  Password: $(YELLOW)cat secrets/waha_dashboard_password.txt$(NC)"

## waha-logs: Show WAHA logs with secret validation
waha-logs:
	@echo "$(BLUE)🔍 WAHA Logs:$(NC)"
	@docker-compose logs waha | grep -E "(🔐|✅|❌|⚠️|🚀)"

## health: Check health of all services
health:
	@echo "$(BLUE)🏥 Health Check:$(NC)"
	@echo -n "  Backend:    "
	@curl -sf http://localhost:8000/health/ > /dev/null && echo "$(GREEN)✅ OK$(NC)" || echo "$(YELLOW)⚠️  Down$(NC)"
	@echo -n "  WAHA:       "
	@curl -sf http://localhost:3000/health > /dev/null && echo "$(GREEN)✅ OK$(NC)" || echo "$(YELLOW)⚠️  Down$(NC)"
	@echo -n "  PostgreSQL: "
	@docker-compose exec -T db pg_isready > /dev/null 2>&1 && echo "$(GREEN)✅ OK$(NC)" || echo "$(YELLOW)⚠️  Down$(NC)"
	@echo -n "  Redis:      "
	@docker-compose exec -T redis redis-cli ping > /dev/null 2>&1 && echo "$(GREEN)✅ OK$(NC)" || echo "$(YELLOW)⚠️  Down$(NC)"

## backup: Backup database and secrets
backup:
	@echo "$(BLUE)💾 Creating backup...$(NC)"
	@mkdir -p backups
	@docker-compose exec -T db pg_dump -U capyvagas_user capyvagas > backups/db_backup_$$(date +%Y%m%d_%H%M%S).sql
	@tar -czf backups/secrets_backup_$$(date +%Y%m%d_%H%M%S).tar.gz secrets/
	@echo "$(GREEN)✅ Backup created in backups/$(NC)"

## lint: Run code linters
lint:
	@echo "$(BLUE)🔍 Running linters...$(NC)"
	@ruff check . || true
	@black --check . || true
	@echo "$(GREEN)✅ Linting completed!$(NC)"

## format: Format code with black
format:
	@echo "$(BLUE)✨ Formatting code...$(NC)"
	@black .
	@echo "$(GREEN)✅ Code formatted!$(NC)"
