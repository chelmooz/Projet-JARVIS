# Linux/macOS only (utilise find, rm, shell one-liners).
# Windows : utilisez JARVIS.bat, ou lancez `python -m pytest tests/` directement.
.PHONY: test lint run clean integration

PY = $(shell [ -f portable_python/linux/python3 ] && echo portable_python/linux/python3 || [ -f portable_python/mac/bin/python3 ] && echo portable_python/mac/bin/python3 || echo python3)

test:
	$(PY) -m pytest tests/ -v

contract-check:
	$(PY) -m pytest tests/test_api_contract.py -v

lint:
	$(PY) -m ruff check .

lint-fix:
	$(PY) -m ruff check --fix .

integration:
	$(PY) -m pytest tests/test_integration_ollama.py -v

run:
	$(PY) jarvis.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache
