.PHONY: install dev demo test lint eval eval-baselines record fixtures-check ui

install:  ## Python deps, Chromium and frontend deps
	uv sync
	uv run playwright install chromium
	cd frontend && npm ci

ui:  ## Build the frontend into frontend/dist (served by `glassbox serve`)
	cd frontend && npm run build

demo: install ui  ## Build everything and open the app on http://127.0.0.1:8000
	uv run glassbox serve

dev:  ## Backend on :8000 plus Vite dev server with hot reload on :5173
	uv run glassbox serve & cd frontend && npm run dev

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	cd frontend && npm run lint

eval:  ## Full comparison: needs ANTHROPIC_API_KEY
	uv run glassbox eval --model claude-sonnet-5-5 --model claude-opus-5-5 --model claude-haiku-5-5 --model random --trials 3

eval-baselines:  ## Baselines only, no API key needed
	uv run glassbox eval --model random --model oracle

record:  ## Re-record Claude fixtures and their expected outcomes (needs ANTHROPIC_API_KEY)
	uv run glassbox eval --model claude-sonnet-5-5 --record fixtures/local --out results

fixtures-check:  ## Replay every recorded fixture set, as CI does
	for dir in fixtures/local/*/; do n=$$(basename $$dir); uv run glassbox eval --model "replay:$${dir%/}" --expect results/local__$$n.json --out eval-out --runs-dir eval-out/runs; done
