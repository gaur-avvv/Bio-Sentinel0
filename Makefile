.PHONY: setup run run-streamlit run-full test eval data lint-check

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

run:
	. .venv/bin/activate && python -m src.api.app

run-streamlit:
	. .venv/bin/activate && streamlit run streamlit_app.py --server.port ${PORT:-8501} --server.address 0.0.0.0

run-full:
	docker compose up --build

test:
	. .venv/bin/activate && python -m pytest -q tests/test_extraction.py

test-realworld:
	. .venv/bin/activate && python -m pytest -q tests/test_realworld_scenarios.py

eval:
	. .venv/bin/activate && python scripts/run_evaluation.py

data:
	. .venv/bin/activate && python scripts/generate_training_data.py

lint-check:
	. .venv/bin/activate && python -m py_compile src/api/app.py src/agents/intake_agent.py src/agents/surveillance_agent.py
