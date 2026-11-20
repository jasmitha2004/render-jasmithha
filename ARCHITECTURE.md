# Architecture Overview

## Layered design
- Presentation: Streamlit UI in `frontend/app.py`
- API: Django REST Framework in `backend/contextbridge_app/views.py` and `urls.py`
- Intelligence layer: service code in `backend/contextbridge_app/services/knowledge_services.py`
- Storage: PostgreSQL (via `DATABASE_URL`) in production, SQLite locally; Django ORM models; uploads on `MEDIA_ROOT`
- Deployment: two Render web services (gunicorn + Streamlit) defined in `render.yaml`

## How the pieces work together
1. The user uploads documents through the Streamlit app.
2. The API stores file metadata and extracts text.
3. The application chunks the extracted text and runs rule-based knowledge extraction.
4. The system detects missing information and calculates readiness.
5. A lightweight project assistant can answer questions using the available evidence.

## Example flow
Upload document -> extract text -> create chunks -> detect risks and gaps -> calculate readiness -> answer user questions -> generate report.

## Design decisions
- Django handles authentication and project-level access.
- Streamlit keeps the interface simple and fast to prototype.
- Service modules isolate business logic. `ClaudeExtractionService` is used only when `ANTHROPIC_API_KEY` is set; every result carries the mode that actually produced it, with automatic rule-based fallback on failure.
