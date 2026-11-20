# ContextBridge AI — repository audit

Audit date: 20 November 2026. Scope is the local Django + Streamlit application. Documentation was compared with the code, not treated as proof that a feature exists.

## 1. Existing implementation

- Authentication: register, session login, and logout in `backend/contextbridge_app/views.py`. Project routes require an authenticated owner.
- Projects, documents (PDF, DOCX, TXT), decisions, tasks, risks, knowledge gaps, readiness, knowledge graph, keyword Q&A, rehearsal questions, and plain-text handover reports are implemented.
- Extraction falls back to local rules when no Anthropic key is configured. `ClaudeExtractionService` and `test_anthropic` exist for the provider connection.
- Streamlit pages cover projects, documents, decisions, gaps, graph, readiness, assistant, rehearsal, reports, settings, and a quick-start guide.
- API tests in `backend/contextbridge_app/tests/test_api.py` cover auth, owner isolation, upload/processing, readiness, reports, and Q&A.

## 2. Missing features

- No workspace-level executive metrics until `GET /api/workspace/overview/` was added in this change. The UI previously issued one request per project per resource.
- No persisted activity feed, notifications, or full-text project search.
- The assistant is keyword retrieval (`mode: local_keyword_match`). It does not synthesize a Claude answer or use FAISS, despite those items appearing in the README as future work.
- No role-based access beyond project owner. Employees are stored but not used as login identities.
- Handover report versions are always stored as version 1. Reports are not listed historically by the API.
- Task status cannot be updated from the UI.

## 3. Bugs

- `ReadinessCalculator` scores dependency clarity with `depends_on.count() >= 0`, which is always true, so that component is always 100 when tasks exist.
- The knowledge graph and several charts used a separate terracotta palette from the product theme.
- The previous overview hero placed dark ink-colored headings on a dark panel.
- `KnowledgeGapDetector` special-cases MongoDB versus PostgreSQL titles, so conflicting-decision detection is demo-specific.

## 4. Security issues

- API views are `csrf_exempt` and rely on session cookies. That is acceptable only for this local demo; a browser client on another origin needs CSRF or token auth.
- `SECRET_KEY` and `DEBUG` must stay out of production defaults. Confirm `.env` is gitignored before sharing the repo.
- Uploaded files are stored on local disk with the original name. There is type checking by extension, not content inspection.
- Authorization is owner-only. A user who learns another project id receives 403, which the tests cover.
- Q&A returns raw document excerpts to the project owner. That is intended, and it should stay scoped to owned projects.

## 5. Recommended improvements

- Keep the executive dashboard bound to `workspace/overview` so KPIs stay measured.
- Fix dependency clarity so the readiness score reflects recorded dependencies.
- List handover reports from the database and increment versions.
- Use Claude only when a key is present, and label the answer mode in the assistant, which the API already does.
- Add task and risk update endpoints before treating Decisions & Tasks as an operating system of record.
- Replace SQLite and synchronous extraction before any multi-user deployment.

## 6. Implementation priorities

1. Executive workspace on real aggregates, with the navigation and visual system used in an evaluation. Done in this change.
2. Correct readiness math and expose report history.
3. Make task and risk records editable, with the same owner checks.
4. Optional Claude synthesis that cites the existing evidence payload.
5. Background processing and a production auth design.

Working upload, extraction, graph, readiness, rehearsal, and report flows were left in place. Quick Start remains under My Projects as Workspace guide.

## 7. Production-readiness audit (Render deployment pass)

Findings below were verified by running the code, not assumed.

**Bugs found and fixed**
- Streamlit created `requests.Session()` at module level; Streamlit re-runs the script on each interaction, so the Django session cookie was discarded and every request after login returned 403. The session now lives in `st.session_state`.
- Report "Download" linked the browser straight to the API, which has no browser session → 403. Now uses `st.download_button` with the report content.
- Document-derived text was injected into `unsafe_allow_html` markup unescaped (stored XSS). All dynamic values are now escaped.
- `extract_decisions` invented MongoDB/PostgreSQL decisions when those words appeared. Removed; the conflicting-technology gap check is generalised (databases, brokers, clouds).
- `start.sh` seed check lacked `DJANGO_SETTINGS_MODULE`, so it always failed and re-seeded on every start.
- `ClaudeExtractionService` was never used for extraction or Q&A. It now is, with validated output and honest mode labels.
- Knowledge-graph labels were dark text on a dark background; badges were light-theme colours on a dark UI.
- `ALLOWED_HOSTS=['*']`, dev `SECRET_KEY` fallback, hard-coded demo credentials pre-filled in the login form.
- Unused heavyweight dependencies (`sentence-transformers`, `faiss-cpu`, `pydantic`, `numpy`) were never imported; removed (they pull in PyTorch and would exceed free-tier build limits). `requirements.txt` had a stray leading space and `PyMuPDF>=1.9.0` was unrealistic.

**Corrections to earlier sections of this file:** the dependency-clarity bug in section 3 is already fixed in code (`ReadinessCalculator` checks `depends_on.exists()`), and handover versions already increment and are listed by `/reports/`.

**Known limitations (not changed)**
- The readiness score subtracts a gap penalty (up to 40 points) for gaps that are themselves derived from the same missing rationale/owner/mitigation data, so those weaknesses are partly counted twice. A small project can score 0.
- Rule-based extraction can emit near-duplicate decisions when several regex patterns match one sentence.
- Extraction is synchronous inside the request; large documents need a background worker.
- Task/risk records cannot be edited from the UI.
