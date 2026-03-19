.PHONY: install run run-no-hud test lint status query reset

install:
	pip install -e ".[dev]"
	ollama pull mistral

run:
	synapse start

run-no-hud:
	synapse start --no-hud

test:
	pytest tests/ -v

lint:
	ruff check synapse/ cli/ tests/
	ruff format --check synapse/ cli/ tests/

format:
	ruff format synapse/ cli/ tests/

status:
	synapse status

query:
	@read -p "Query: " q; synapse query "$$q"

reset:
	synapse reset-memory --yes
