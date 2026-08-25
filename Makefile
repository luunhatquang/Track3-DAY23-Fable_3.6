PYTHON ?= python3

.PHONY: install install-google install-openai install-anthropic install-ui test lint typecheck run-scenarios grade-local clean

install:
	$(PYTHON) -m pip install -e '.[dev,sqlite]'

install-google:
	$(PYTHON) -m pip install -e '.[google]'

install-openai:
	$(PYTHON) -m pip install -e '.[openai]'

install-anthropic:
	$(PYTHON) -m pip install -e '.[anthropic]'

install-ui:
	$(PYTHON) -m pip install -e '.[ui]'

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

typecheck:
	$(PYTHON) -m mypy src

run-scenarios:
	$(PYTHON) -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json

grade-local:
	$(PYTHON) -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build *.egg-info outputs/*.json
