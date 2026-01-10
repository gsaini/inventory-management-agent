# Inventory Management Agent - Makefile
# Quick commands for development workflow

.PHONY: help setup install dev prod seed test lint format clean docker-up docker-down

# Default target
help:
	@echo "Inventory Management Agent"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  setup      First-time project setup"
	@echo "  install    Install dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  dev        Start development server"
	@echo "  prod       Start production server"
	@echo "  seed       Seed database with sample data"
	@echo "  test       Run test suite"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint       Run linters (ruff)"
	@echo "  format     Format code (black, isort)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up    Start PostgreSQL in Docker"
	@echo "  docker-down  Stop PostgreSQL container"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean      Remove cache and build files"
	@echo ""

# Setup
setup:
	@./scripts/start.sh setup

install:
	pip install -e ".[dev]"

# Development
dev:
	@./scripts/start.sh dev

prod:
	@./scripts/start.sh prod

seed:
	@./scripts/start.sh seed

test:
	pytest tests/ -v --tb=short

# Code Quality
lint:
	ruff check src/ tests/

format:
	black src/ tests/ scripts/
	isort src/ tests/ scripts/

# Docker (PostgreSQL)
docker-up:
	docker run -d \
		--name inventory-postgres \
		-e POSTGRES_USER=inventory \
		-e POSTGRES_PASSWORD=inventory123 \
		-e POSTGRES_DB=inventory_db \
		-p 5432:5432 \
		postgres:15-alpine
	@echo "PostgreSQL started on localhost:5432"
	@echo "Connection: postgresql://inventory:inventory123@localhost:5432/inventory_db"

docker-down:
	docker stop inventory-postgres || true
	docker rm inventory-postgres || true

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned up cache files"
