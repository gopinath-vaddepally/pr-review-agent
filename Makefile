.PHONY: help build up down logs test clean

help:
	@echo "Azure DevOps PR Review Agent - Development Commands"
	@echo ""
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View service logs"
	@echo "  make test     - Run test suite"
	@echo "  make clean    - Clean up containers and volumes"
	@echo ""

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Services started. API available at http://localhost:8000"
	@echo "Check health: curl http://localhost:8000/health"

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	pytest

clean:
	docker-compose down -v
	rm -rf build/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
