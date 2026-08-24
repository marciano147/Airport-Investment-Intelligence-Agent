.PHONY: setup run test compile smoke e2e check clean

PYTHON ?= python
VENV_PYTHON := .venv/bin/python
VENV_PIP := .venv/bin/pip
VENV_STREAMLIT := .venv/bin/streamlit

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PIP) install -r requirements.txt

run:
	$(VENV_STREAMLIT) run app.py

test:
	$(VENV_PYTHON) -m pytest tests/ -v

compile:
	$(VENV_PYTHON) -m compileall app.py agent.py tools.py data_loader.py prompts.py scoring.py long_haul.py voice_utils.py chat_store.py tests scripts

smoke:
	$(VENV_PYTHON) scripts/live_smoke.py

e2e:
	$(VENV_PYTHON) scripts/e2e_edge_cases.py

check: test compile
	git diff --check

clean:
	$(VENV_PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(p) for p in Path('.').rglob('__pycache__')]; p=Path('.pytest_cache'); shutil.rmtree(p) if p.exists() else None"
