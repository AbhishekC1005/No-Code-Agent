.PHONY: build run install dev clean

build:
	python build.py

install:
	pip install -e .

run:
	nocode-agent start

dev-backend:
	uvicorn nocode_agent.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

clean:
	rm -rf frontend/dist backend/nocode_agent/static
