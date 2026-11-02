# Protected MongoDB API

Python 3.11+ is required. Use a dedicated demonstration database/collection. This is a single-owner token API, not multi-user authentication.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r backend/requirements-dev.lock.txt
python -m pytest -q backend
python -m black --check backend
python -m pylint --rcfile backend/pyproject.toml backend/server.py backend/wsgi.py
```

Set `MONGODB_URI`, `API_ADMIN_TOKEN` (random owner-chosen secret of at least 32 characters), `MONGODB_DATABASE` and `MONGODB_COLLECTION` in the server environment. Never commit those values or put them in site files. `ALLOWED_ORIGIN` defaults to https://subhashdixit.github.io. Configure least-privilege database access and normal TLS certificate validation; the code does not disable certificate checks.

```bash
gunicorn --chdir backend --bind 127.0.0.1:8001 --workers 1 --threads 4 wsgi:app
```

For Render, create a Python Web Service from this repository on the Free plan. Build: `python -m pip install --require-hashes --only-binary=:all: -r backend/requirements.lock.txt`. Start: `gunicorn --chdir backend --bind 0.0.0.0:$PORT --workers 1 --threads 4 wsgi:app`. Set Python 3.11+, the environment values above and health path `/health/ready`. Verify `mongo_configured:true` and a real CRUD request against your dedicated collection before treating server mode as available. Free hosting can sleep and is subject to provider limits; MongoDB is a separately configured service. No server deployment or existing collection is silently connected by the Pages UI.

API routes:

- `GET /health/ready`: configuration/reachability status, no secrets.
- `GET /api/documents`: list up to 500 app documents.
- `POST /api/documents`: `{ "document": { ... } }`, returns generated UUID.
- `PUT /api/documents/<uuid>`: replace document content using the same body.
- `DELETE /api/documents/<uuid>`: remove that exact record.

All `/api/` calls require `Authorization: Bearer <your-token>`. This grants full access to the dedicated collection; never share it in a public demo. Body ≤64,000 bytes; document ≤30,000 characters; no operator/dotted/prototype keys. Errors do not expose driver/URI details. Responses are no-store. CORS permits the configured origin but is not authentication.

CI starts an isolated MongoDB service and sets `MONGO_TEST_URI`; the integration test creates a uniquely named synthetic collection, exercises the complete CRUD route contract, then removes only that disposable collection. Without a dedicated test URI, local backend route tests use an isolated in-memory test double and the live-driver test is explicitly skipped.

Exact runtime versions, installer lock and the complete distribution index are in [DEPENDENCIES.md](../DEPENDENCIES.md).
