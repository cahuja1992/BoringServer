"""Makefile-style commands for common tasks."""

.PHONY: help install install-dev test lint format clean docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install       - Install package"
	@echo "  make install-dev   - Install package with dev dependencies"
	@echo "  make test          - Run tests"
	@echo "  make test-cov      - Run tests with coverage"
	@echo "  make lint          - Run linters"
	@echo "  make format        - Format code"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest tests/unit/ -v

test-cov:
	pytest tests/ -v --cov=engine --cov=models --cov-report=html --cov-report=term-missing

test-integration:
	pytest tests/integration/ -v

lint:
	flake8 engine/ tests/
	mypy engine/ --ignore-missing-imports
	black --check engine/ tests/
	isort --check-only engine/ tests/

format:
	black engine/ tests/
	isort engine/ tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker build -t inference-engine:latest .

docker-run:
	docker-compose up
