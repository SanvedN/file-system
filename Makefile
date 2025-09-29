# Multi-Tenant Async File Management and Extraction System
# Development and deployment automation

.PHONY: help install dev-setup test docker-up deploy-k8s clean

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker-compose
KUBECTL := kubectl
PROJECT_NAME := file-system
NAMESPACE := file-system

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Multi-Tenant File Management System$(NC)"
	@echo "$(BLUE)=====================================$(NC)"
	@echo ""
	@echo "$(GREEN)Available commands:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development Setup
install: ## Install Python dependencies
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)Dependencies installed successfully!$(NC)"

dev-setup: install ## Setup development environment
	@echo "$(BLUE)Setting up development environment...$(NC)"
	cp env.example .env || echo "env.example not found, please create .env manually"
	mkdir -p logs storage
	@echo "$(GREEN)Development environment setup complete!$(NC)"

install-dev: ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	$(PIP) install -e ".[dev]"
	@echo "$(GREEN)Development dependencies installed!$(NC)"

# Testing
test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	pytest

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	pytest -m "unit"

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest -m "integration"

test-async: ## Run async tests only
	@echo "$(BLUE)Running async tests...$(NC)"
	pytest -m "async"

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest --cov=src --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)Coverage report generated in htmlcov/$(NC)"

test-watch: ## Run tests in watch mode
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	pytest-watch

# Code Quality
lint: ## Run linting
	@echo "$(BLUE)Running linters...$(NC)"
	black --check src/ tests/
	isort --check-only src/ tests/
	mypy src/
	ruff check src/ tests/

format: ## Format code
	@echo "$(BLUE)Formatting code...$(NC)"
	black src/ tests/
	isort src/ tests/
	@echo "$(GREEN)Code formatted successfully!$(NC)"

format-check: ## Check code formatting
	@echo "$(BLUE)Checking code formatting...$(NC)"
	black --check src/ tests/
	isort --check-only src/ tests/

# Development Services
dev-start: ## Start development services
	@echo "$(BLUE)Starting development services...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d postgres redis
	@echo "$(GREEN)Development services started!$(NC)"

dev-stop: ## Stop development services
	@echo "$(BLUE)Stopping development services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Development services stopped!$(NC)"

dev-restart: dev-stop dev-start ## Restart development services

# Database Operations
migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.db import init_db; asyncio.run(init_db())"
	@echo "$(GREEN)Database migrations completed!$(NC)"

db-shell: ## Connect to database shell
	@echo "$(BLUE)Connecting to database...$(NC)"
	$(DOCKER_COMPOSE) exec postgres psql -U file_system_user -d file_system_db

db-reset: ## Reset database (WARNING: Destroys all data)
	@echo "$(RED)WARNING: This will destroy all data!$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) up -d postgres redis
	sleep 10
	$(MAKE) migrate
	@echo "$(GREEN)Database reset completed!$(NC)"

redis-shell: ## Connect to Redis shell
	@echo "$(BLUE)Connecting to Redis...$(NC)"
	$(DOCKER_COMPOSE) exec redis redis-cli

# Advanced Migration operations
migrate-init: ## Initialize database with Alembic migrations
	@echo "$(BLUE)Initializing database with Alembic migrations...$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import initialize_database_migrations; asyncio.run(initialize_database_migrations())"

migrate-upgrade: ## Upgrade database to latest migration
	@echo "$(BLUE)Upgrading database to latest migration...$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import upgrade_database_migrations; asyncio.run(upgrade_database_migrations())"

migrate-status: ## Check migration status
	@echo "$(BLUE)Checking migration status...$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import check_database_migration_status; print(asyncio.run(check_database_migration_status()))"

migrate-create: ## Create a new migration (usage: make migrate-create MESSAGE="description")
	@echo "$(BLUE)Creating new migration: $(MESSAGE)$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import create_database_migration; print(asyncio.run(create_database_migration('$(MESSAGE)')))"

migrate-downgrade: ## Downgrade database (usage: make migrate-downgrade REVISION="revision_id")
	@echo "$(RED)Downgrading database to revision: $(REVISION)$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import get_migration_manager; asyncio.run(get_migration_manager().downgrade_database('$(REVISION)'))"

migrate-history: ## Show migration history
	@echo "$(BLUE)Migration history:$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import get_migration_manager; print(asyncio.run(get_migration_manager().get_migration_history()))"

migrate-reset: ## Reset database with migrations (WARNING: This will delete all data)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	$(PYTHON) -c "import asyncio; from src.shared.migrations import get_migration_manager; asyncio.run(get_migration_manager().reset_database())"

migrate-validate: ## Validate all migrations
	@echo "$(BLUE)Validating migrations...$(NC)"
	$(PYTHON) -c "import asyncio; from src.shared.migrations import get_migration_manager; print('Valid:', asyncio.run(get_migration_manager().validate_migrations()))"

# Docker Operations
docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker build --target file-service -t $(PROJECT_NAME)-file-service:latest .
	docker build --target extraction-service -t $(PROJECT_NAME)-extraction-service:latest .
	docker build --target api-gateway -t $(PROJECT_NAME)-api-gateway:latest .
	@echo "$(GREEN)Docker images built successfully!$(NC)"

docker-up: ## Start all services with Docker Compose
	@echo "$(BLUE)Starting all services with Docker Compose...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)All services started! Check status with 'make docker-status'$(NC)"

docker-down: ## Stop all Docker services
	@echo "$(BLUE)Stopping all Docker services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)All Docker services stopped!$(NC)"

docker-logs: ## View Docker service logs
	@echo "$(BLUE)Viewing Docker service logs...$(NC)"
	$(DOCKER_COMPOSE) logs -f

docker-status: ## Check Docker service status
	@echo "$(BLUE)Docker service status:$(NC)"
	$(DOCKER_COMPOSE) ps

deploy-docker: docker-build ## Deploy with Docker Compose (production)
	@echo "$(BLUE)Deploying with Docker Compose...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d
	@echo "$(GREEN)Deployment completed!$(NC)"

# Kubernetes Operations
k8s-create-namespace: ## Create Kubernetes namespace
	@echo "$(BLUE)Creating Kubernetes namespace...$(NC)"
	$(KUBECTL) apply -f k8s/namespace.yaml

deploy-k8s: k8s-create-namespace ## Deploy to Kubernetes
	@echo "$(BLUE)Deploying to Kubernetes...$(NC)"
	$(KUBECTL) apply -f k8s/
	@echo "$(GREEN)Kubernetes deployment completed!$(NC)"

k8s-status: ## Check Kubernetes deployment status
	@echo "$(BLUE)Kubernetes deployment status:$(NC)"
	$(KUBECTL) get all -n $(NAMESPACE)

k8s-logs: ## View Kubernetes service logs
	@echo "$(BLUE)Kubernetes service logs:$(NC)"
	$(KUBECTL) logs -n $(NAMESPACE) -l app=file-service --tail=100 -f

k8s-shell: ## Connect to Kubernetes pod shell
	@echo "$(BLUE)Connecting to Kubernetes pod...$(NC)"
	$(KUBECTL) exec -it -n $(NAMESPACE) deployment/file-service -- /bin/bash

k8s-delete: ## Delete Kubernetes deployment
	@echo "$(RED)Deleting Kubernetes deployment...$(NC)"
	$(KUBECTL) delete namespace $(NAMESPACE)

# Service Operations
start-file-service: ## Start File Service locally
	@echo "$(BLUE)Starting File Service...$(NC)"
	$(PYTHON) -m uvicorn src.file_service.app:app --host 0.0.0.0 --port 8001 --reload

start-extraction-service: ## Start Extraction Service locally
	@echo "$(BLUE)Starting Extraction Service...$(NC)"
	$(PYTHON) -m uvicorn src.extraction_service.app:app --host 0.0.0.0 --port 8002 --reload

start-api-gateway: ## Start API Gateway locally
	@echo "$(BLUE)Starting API Gateway...$(NC)"
	$(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Monitoring and Logs
logs: ## View service logs
	@echo "$(BLUE)Service logs:$(NC)"
ifdef service
	$(DOCKER_COMPOSE) logs -f $(service)
else
	$(DOCKER_COMPOSE) logs -f
endif

health: ## Check service health
	@echo "$(BLUE)Checking service health...$(NC)"
	@curl -f http://localhost:8001/api/v1/health || echo "$(RED)File Service: UNHEALTHY$(NC)"
	@curl -f http://localhost:8002/api/v1/health || echo "$(RED)Extraction Service: UNHEALTHY$(NC)"
	@curl -f http://localhost:8000/health || echo "$(RED)API Gateway: UNHEALTHY$(NC)"

metrics: ## View service metrics
	@echo "$(BLUE)Service metrics:$(NC)"
	@curl -s http://localhost:8001/api/v1/files/stats/global | jq . || echo "File Service metrics unavailable"
	@curl -s http://localhost:8002/api/v1/extractions/stats/global | jq . || echo "Extraction Service metrics unavailable"

# Backup and Maintenance
backup: ## Backup database
	@echo "$(BLUE)Creating database backup...$(NC)"
	mkdir -p backups
	$(DOCKER_COMPOSE) exec -T postgres pg_dump -U file_system_user file_system_db > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backup created in backups/$(NC)"

restore: ## Restore database from backup (Usage: make restore backup=backup_file.sql)
	@echo "$(BLUE)Restoring database from backup...$(NC)"
ifndef backup
	@echo "$(RED)Error: Please specify backup file. Usage: make restore backup=backup_file.sql$(NC)"
	@exit 1
endif
	$(DOCKER_COMPOSE) exec -T postgres psql -U file_system_user -d file_system_db < $(backup)
	@echo "$(GREEN)Database restored from $(backup)$(NC)"

cleanup-extractions: ## Cleanup old extraction records
	@echo "$(BLUE)Cleaning up old extractions...$(NC)"
	curl -X POST "http://localhost:8002/api/v1/extractions/admin/cleanup?days_old=30&keep_successful=true"
	@echo "$(GREEN)Extraction cleanup completed!$(NC)"

# Utility Commands
clean: ## Clean up generated files and containers
	@echo "$(BLUE)Cleaning up...$(NC)"
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -f
	rm -rf __pycache__ .pytest_cache .coverage htmlcov/ .mypy_cache/
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)Cleanup completed!$(NC)"

docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	mkdocs build
	@echo "$(GREEN)Documentation generated in site/$(NC)"

docs-serve: ## Serve documentation locally
	@echo "$(BLUE)Serving documentation at http://localhost:8080$(NC)"
	mkdocs serve -a 0.0.0.0:8080

# CI/CD Commands
ci-test: ## Run CI test suite
	@echo "$(BLUE)Running CI test suite...$(NC)"
	$(MAKE) lint
	$(MAKE) test-coverage
	@echo "$(GREEN)CI tests passed!$(NC)"

ci-build: ## Build for CI/CD
	@echo "$(BLUE)Building for CI/CD...$(NC)"
	$(MAKE) docker-build
	@echo "$(GREEN)CI build completed!$(NC)"

# Production Commands
production-deploy: ## Deploy to production
	@echo "$(RED)Deploying to production...$(NC)"
	@read -p "Are you sure you want to deploy to production? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	$(MAKE) deploy-k8s
	@echo "$(GREEN)Production deployment completed!$(NC)"

production-rollback: ## Rollback production deployment
	@echo "$(RED)Rolling back production deployment...$(NC)"
	$(KUBECTL) rollout undo deployment/file-service -n $(NAMESPACE)
	$(KUBECTL) rollout undo deployment/extraction-service -n $(NAMESPACE)
	@echo "$(GREEN)Production rollback completed!$(NC)"

# Environment Information
env-info: ## Show environment information
	@echo "$(BLUE)Environment Information:$(NC)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$($(DOCKER_COMPOSE) --version)"
	@echo "Kubectl: $$($(KUBECTL) version --client --short 2>/dev/null || echo 'Not installed')"
	@echo "Project: $(PROJECT_NAME)"
	@echo "Namespace: $(NAMESPACE)"

# Quick Start
quickstart: dev-setup docker-up migrate ## Quick start for new developers
	@echo "$(GREEN)Quick start completed!$(NC)"
	@echo "$(BLUE)Services available at:$(NC)"
	@echo "  File Service API: http://localhost:8001/docs"
	@echo "  Extraction Service API: http://localhost:8002/docs"
	@echo "  API Gateway: http://localhost:8000/docs"
	@echo ""
	@echo "$(BLUE)Next steps:$(NC)"
	@echo "  1. Check service health: make health"
	@echo "  2. View logs: make logs"
	@echo "  3. Run tests: make test"
