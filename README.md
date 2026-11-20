# ContextBridge AI — Enterprise Knowledge Continuity Platform

_By Jasmitha Gutha._ See `docs/HOW_IT_WORKS.md`, `docs/DEPLOY_ANYWHERE.md`, the static demo in `demo/`, and the landing site in `landing/`.

Upload project documents, extract **decisions, tasks and risks**, detect **knowledge gaps**, score **handover readiness**, explore a **knowledge graph**, ask **evidence-backed questions**, and generate **handover reports**.

## Landing page

`landing/index.html` is a static marketing page with a 3D (Three.js) hero. Its buttons link to the Streamlit app via `landing/config.js`; the app links back through `CONTEXTBRIDGE_SITE_URL`. Preview locally with `python -m http.server 8080 --directory landing`. Deployed as the `contextbridge-landing` static site in `render.yaml`. Preview figures on the page are labelled sample data.

## Architecture

```
Browser ──► Streamlit (frontend/app.py)  ──HTTPS──►  Django REST API (backend/)  ──►  PostgreSQL (prod) / SQLite (local)
              per-user requests.Session                 gunicorn + WhiteNoise              │
              holds the Django session cookie                                              └─► optional: Anthropic API
```

* The browser only talks to Streamlit. Streamlit calls the API server-to-server and keeps the Django session cookie inside each user's Streamlit session.
* Services: `backend/contextbridge_app/services/knowledge_services.py` (extraction, gaps, readiness, Q&A, optional Claude).

## Technologies

Django 4.2 · Django REST Framework · Streamlit · PostgreSQL / SQLite · gunicorn · WhiteNoise · dj-database-url · PyMuPDF · python-docx · NetworkX + Plotly · Anthropic SDK (optional)

## AI implementation — what is real

| Feature | Without `ANTHROPIC_API_KEY` | With a valid key |
|---|---|---|
| Decision / task / risk extraction | Regex rules (`rule_based`) | Claude JSON extraction, validated and clamped (`claude`) |
| Question answering | Keyword retrieval over document chunks (`local_keyword_match`) | Claude synthesises an answer **only from the retrieved excerpts** (`claude`) |
| Knowledge gaps, readiness, graph, reports | Deterministic code | Deterministic code (not LLM-generated) |

If Claude is configured but a call fails (bad key, timeout, malformed JSON), the app falls back to the rule-based result and reports `rule_based_fallback`. The UI shows a badge stating which method produced each result — it never claims an LLM was used when it was not. The key is read from the environment only and is never returned by any endpoint or logged.

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # placeholders only; edit as needed

# Terminal 1 — backend
cd backend
python manage.py migrate
python sample_data_generator.py                       # optional demo user + sample project
python manage.py runserver 0.0.0.0:8000

# Terminal 2 — frontend (from repo root)
streamlit run frontend/app.py
```

Or run everything with `./start.sh`. Open <http://localhost:8501>. Demo user: `demo` (password from `DEMO_PASSWORD`, default `DemoPass123` — set `CONTEXTBRIDGE_DEMO_MODE=true` to pre-fill the login form locally).

### Backend only / frontend only
* Backend: `cd backend && python manage.py runserver` → API at `http://127.0.0.1:8000/api`, health at `/health/`.
* Frontend: `CONTEXTBRIDGE_API=https://your-api-host/api streamlit run frontend/app.py`.

## Environment variables

| Variable | Service | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | backend | **Required when `DJANGO_DEBUG=False`** (app refuses to start with the dev key) |
| `DJANGO_DEBUG` | backend | `True` locally, `False` in production |
| `DJANGO_ALLOWED_HOSTS` | backend | Comma-separated hosts (Render hostname is added automatically) |
| `CSRF_TRUSTED_ORIGINS` | backend | Comma-separated `https://…` origins |
| `DATABASE_URL` | backend | PostgreSQL URL; unset → SQLite |
| `SQLITE_PATH` | backend | Override SQLite file location |
| `MEDIA_ROOT` | backend | Upload directory (use a persistent disk on Render) |
| `MAX_UPLOAD_MB` | backend | Upload size cap (default 10) |
| `ANTHROPIC_API_KEY` | backend | Optional; enables Claude |
| `ANTHROPIC_MODEL` | backend | Model id (default `claude-sonnet-4-5`) |
| `SEED_DEMO_DATA`, `DEMO_PASSWORD` | backend | Render: seed the demo account on start |
| `SECURE_SSL_REDIRECT`, `SECURE_COOKIES` | backend | Default on in production; disable only to simulate production over http locally |
| `CONTEXTBRIDGE_API` | frontend | Backend API base URL, e.g. `https://contextbridge-backend.onrender.com/api` |
| `CONTEXTBRIDGE_API_TIMEOUT` | frontend | Seconds (default 60, covers Render cold starts) |
| `CONTEXTBRIDGE_DEMO_MODE` | frontend | Pre-fill demo credentials (default off) |

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/`, `/api/health/` | Liveness + DB check (public) |
| POST | `/api/auth/register/`, `/login/`, `/logout/` · GET `/auth/me/` | Auth (session) |
| GET/POST | `/api/projects/` · GET/PUT/DELETE `/api/projects/<id>/` | Projects |
| GET/POST | `/api/projects/<id>/documents/` | List / upload (PDF, DOCX, TXT) |
| POST | `/api/projects/<id>/process/` | Extract knowledge; returns `extraction_mode` |
| GET | `/api/projects/<id>/decisions/ tasks/ risks/ knowledge-gaps/ knowledge-graph/ readiness/` | Intelligence |
| POST | `/api/projects/<id>/ask/` | Evidence-backed Q&A; returns `mode` |
| POST | `/api/projects/<id>/rehearsals/` · `/handover/` | Rehearsal questions / report |
| GET | `/api/projects/<id>/reports/` · `/api/handover/<id>/download/` | Report history / download |
| GET | `/api/workspace/overview/` | Executive KPIs |

Details: [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## Deploy on Render (Blueprint)

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → select the repo. `render.yaml` creates a PostgreSQL database and two web services.
3. When prompted, set `DEMO_PASSWORD` and (optionally) `ANTHROPIC_API_KEY`.
4. After the first deploy, open the backend's `…/health/` URL; it should return `{"status":"ok",…}`.
5. If Render gave the backend a URL different from `https://contextbridge-backend.onrender.com`, update on **both** services: `CONTEXTBRIDGE_API` (frontend, ending `/api`), and `DJANGO_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` (backend). Redeploy.

| Service | Build | Start |
|---|---|---|
| backend | `pip install -r requirements.txt && cd backend && python manage.py collectstatic --noinput` | `cd backend && python manage.py migrate --noinput && ([ "$SEED_DEMO_DATA" != "true" ] \|\| python sample_data_generator.py) && gunicorn contextbridge.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
| frontend | `pip install -r requirements.txt` | `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |

**Free-tier caveats:** services sleep when idle (first request can take ~50 s); free Postgres expires after 30 days; the free web filesystem is ephemeral, so uploaded files disappear on redeploy (extracted decisions/tasks/chunks stay in the database). Attach a Render Disk and set `MEDIA_ROOT` for persistent uploads.

## Tests

```bash
cd backend && pytest        # 18 tests: auth, isolation, upload hardening, AI honesty/fallback, reports, health
```

## Troubleshooting

* **"Cannot reach the ContextBridge API"** — check `CONTEXTBRIDGE_API` (must be the backend's public https URL ending in `/api`) and that the backend is live.
* **Timeout on first request** — the free backend is waking up; retry after ~1 minute.
* **Backend 400 "Bad Request (400)"** — host not in `DJANGO_ALLOWED_HOSTS`.
* **Backend refuses to start** — `DJANGO_SECRET_KEY` is missing/placeholder while `DJANGO_DEBUG=False`.
* **Signed out unexpectedly** — session expired or backend restarted; sign in again.
* **Assistant badge says "Rule-based (Claude failed)"** — check the key/model; see backend logs (`contextbridge.ai`).

## Live demo

Frontend: `https://contextbridge-frontend.onrender.com` (after deploy). Sign in as `demo`, open **Workspace overview**, then **Documents → Process**, **Risk intelligence**, **Knowledge gaps**, **Knowledge graph**, **Readiness**, ask a question in **AI assistant**, and generate a **Report**.

## Security notes
* Secrets come from the environment; `.env` is git-ignored; `.env.example` has placeholders only.
* API views use session auth with CSRF enforcement disabled because the API is called server-to-server by Streamlit. If you call it from browser JavaScript, switch to token auth or re-enable CSRF.
* All API-derived text is HTML-escaped in the UI; uploads are size-limited, extension-checked and filename-sanitised.
