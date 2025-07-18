.PHONY: install test clean run-tests coverage lint format install-cuda

install:
	uv venv
	uv pip install -e ".[dev]"
	@echo ""
	@echo "Base installation complete!"
	@echo "To install CUDA support for LLMs, run: make install-cuda"

install-cuda:
	. .venv/bin/activate && CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python>=0.2.50
	@echo "CUDA support installed!"

test:
	. .venv/bin/activate && python -m pytest tests/ -v

test-cov:
	. .venv/bin/activate && python -m pytest tests/ --cov=src --cov-report=term-missing

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage

format:
	. .venv/bin/activate && black src/ tests/

run:
	. .venv/bin/activate && python -m src.cli

help:
	@echo "Available targets:"
	@echo "  install      - Create virtual environment and install dependencies"
	@echo "  install-cuda - Install CUDA support for LLMs (run after install)"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  clean        - Clean up cache and temporary files"
	@echo "  format       - Format code with black"
	@echo "  run          - Run the CLI" 