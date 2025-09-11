.PHONY: test clean run-tests coverage lint format run sync frontend-test

sync:
	uv venv
	uv pip install -e ".[dev]"

test:
	. .venv/bin/activate && python -m pytest tests/ -v
	cd frontend && bash -lc 'source ~/.nvm/nvm.sh >/dev/null 2>&1 || true; if [ -f .nvmrc ]; then nvm install --silent >/dev/null 2>&1 || true; nvm use --silent >/dev/null 2>&1 || true; fi; npm ci --silent || npm install --silent; npm run -s test'

test-cov:
	. .venv/bin/activate && python -m pytest tests/ --cov=src --cov-report=term-missing

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage

format:
	. .venv/bin/activate && black src/ tests/

run:
	. .venv/bin/activate && honcho start

help:
	@echo "Available targets:"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  clean        - Clean up cache and temporary files"
	@echo "  format       - Format code with black"
	@echo "  run          - Run the CLI" 
