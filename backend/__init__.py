from importlib.util import find_spec

if missing := [m for m in ("fastapi", "httpx", "dotenv", "qdrant_client") if not find_spec(m)]:
    raise SystemExit(f"\nMissing packages: {', '.join(missing)}. You are probably not using the project's Python.\n"
                     "Run it with:  venv\\Scripts\\python -m uvicorn backend.main:app --port 8000\n"
                     "Or first run: venv\\Scripts\\python -m pip install -r requirements.txt\n")
