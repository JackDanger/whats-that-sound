web: bash -lc 'source ~/.nvm/nvm.sh >/dev/null 2>&1 || true; cd frontend && if [ -f .nvmrc ]; then nvm install --silent >/dev/null 2>&1 || true; nvm use --silent >/dev/null 2>&1 || true; fi; npm run dev'
api: ./.venv/bin/python -m uvicorn src.server:app_factory --host 0.0.0.0 --port 8000 --reload --factory --timeout-keep-alive 5
worker-scan: ./.venv/bin/python -m src.worker scan --reload --poll-seconds 300
worker-analyze: ./.venv/bin/python -m src.worker analyze --reload --poll-seconds 5
worker-move: ./.venv/bin/python -m src.worker move --reload --poll-seconds 5

