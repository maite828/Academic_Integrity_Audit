.PHONY: install setup-ai run app stop docker-up docker-down test

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e .

setup-ai:
	scripts/setup_ai_local.sh llama3.1

run:
	scripts/run_local.sh

app:
	scripts/start_local.sh

stop:
	scripts/stop_local.sh

docker-up:
	docker compose up --build

docker-down:
	docker compose down

test:
	.venv/bin/python -m compileall -q src
