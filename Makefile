.PHONY: install install-cuda test clean run-tests coverage lint format

install:
	uv venv
	uv pip install -e ".[dev]"
	export CUDA_HOME=/usr/local/cuda && \
	export PATH=/usr/local/cuda/bin:$$PATH && \
	CMAKE_ARGS="-DGGML_CUDA=on -DGGML_OPENMP=off -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc" GGML_CCACHE=OFF uv pip install 'llama-cpp-python>=0.2.50' --force-reinstall --no-cache-dir
	@echo ""
	@echo "Installation complete with CUDA support!"

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
	@echo "  install      - Create virtual environment and install dependencies (requires CUDA)"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  clean        - Clean up cache and temporary files"
	@echo "  format       - Format code with black"
	@echo "  run          - Run the CLI" 
