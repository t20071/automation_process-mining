# Build Tasks

## Phase 0 — Conda Environment & Scaffold
- [ ] Create conda env with Python 3.11 in ./venv
- [ ] Create .gitignore
- [ ] Create .env.example
- [ ] Create pyproject.toml
- [ ] Create requirements.txt
- [ ] Create Makefile (conda-aware)
- [ ] Create .streamlit/config.toml
- [ ] Create src/process_agent package structure (__init__.py files)
- [ ] Create src/process_agent/config.py
- [ ] Create src/process_agent/logging_config.py
- [ ] Create data/ and audit/ directories

## Phase 1 — Log Generator
- [ ] src/process_agent/generators/log_generator.py
- [ ] tests/test_log_generator.py

## Phase 2 — Process Mining
- [ ] src/process_agent/mining/process_mining.py
- [ ] tests/test_process_mining.py

## Phase 3 — Agent + Gate Engine
- [ ] src/process_agent/agent/llm_client.py
- [ ] src/process_agent/agent/gate_engine.py
- [ ] tests/test_gate_engine.py
- [ ] tests/test_integration.py

## Phase 4 — Streamlit UI
- [ ] src/process_agent/ui/theme.py
- [ ] src/process_agent/ui/dashboard.py
- [ ] app.py

## Phase 5 — Documentation
- [ ] README.md
- [ ] DEPLOYMENT.md

## Phase 6 — Install deps & run tests
- [ ] conda install / pip install deps into env
- [ ] pytest passes all tests
