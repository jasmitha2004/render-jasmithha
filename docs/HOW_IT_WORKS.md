# ContextBridge AI — How it works

**Author:** Jasmitha Gutha
**Project:** ContextBridge AI — Enterprise Knowledge Continuity Platform

## What it does
Teams lose knowledge when people leave or projects change hands. ContextBridge AI takes project documents and turns them into structured knowledge: decisions, tasks and risks, with the sentence each came from. It then finds gaps, scores handover readiness, draws a knowledge graph, answers questions with sources, and generates a handover report.

## Parts of this package
| Folder | What it is | Runs on |
|---|---|---|
| `backend/` | Django REST API: auth, projects, documents, extraction, gaps, graph, Q&A, readiness, reports | Python 3.12, gunicorn, PostgreSQL (prod) / SQLite (local) |
| `frontend/app.py` | Streamlit web app (the working product UI) that calls the API | Python |
| `landing/` | Static marketing website with a 3D hero (Three.js). Buttons link to the app | Any static host |
| `demo/index.html` | Single-file demo app (browser only, no server). Demo login: `demo` / `demo1234` | Any static host |
| `previews/` | Screenshots of the landing page | — |
| `render.yaml` | Render Blueprint: API + Streamlit app + landing site + database | Render |

## Request flow
Browser → Streamlit (`frontend/app.py`) → Django REST API (`/api/...`) → database.
Streamlit keeps the Django session cookie per user. Endpoints include: `auth/login`, `projects`, `projects/<id>/documents`, `process`, `decisions`, `tasks`, `risks`, `knowledge-gaps`, `knowledge-graph`, `ask`, `readiness`, `handover`, `reports`.

## What is AI and what is not
- Extraction: rule-based (regex) by default. With `ANTHROPIC_API_KEY` set, Claude extracts and answers from retrieved excerpts only. The UI shows which method produced each result.
- Q&A without a key: keyword retrieval over document chunks, always with sources.
- Knowledge gaps, readiness score, graph and reports: deterministic code, not an LLM.
- If Claude fails, the app falls back to rules and says so.

## Run locally
```
cd ContextBridge_AI
./start.sh          # Linux/macOS; creates venv, installs, migrates, seeds demo data
```
Website: http://localhost:8080 · App: http://localhost:8501 · API: http://localhost:8000/api
Windows: use WSL or follow the manual steps in `README.md`.
Demo account is created by `backend/sample_data_generator.py` (username `demo`).

## Demo app (no server needed)
Open `demo/index.html` in a browser, or host the `demo/` folder anywhere. It re-implements extraction, Q&A, graph and scoring in the browser using simple rules, for showing the idea without a backend. Data stays in the page and is not saved.

## Known limits
- The demo app accepts .txt and .md only; the Django backend also reads PDF and DOCX.
- Free Render services sleep when idle and the free database expires after 30 days.
- The Streamlit UI does not include the 3D visuals; those are on the landing page.
