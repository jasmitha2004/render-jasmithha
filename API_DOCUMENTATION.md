# API documentation

## Health
### GET /health/  (also /api/health/)
Public. Returns `{"status":"ok","database":"ok","ai_mode":"claude|rule_based"}` (HTTP 503 if the DB is unreachable). Never exposes the API key.

## Authentication
### POST /api/auth/register/
Creates a new user account.

Request body:
```json
{
  "username": "demo_user",
  "email": "demo@example.com",
  "password": "StrongPass123"
}
```

### POST /api/auth/login/
Logs a user in and returns user metadata.

### POST /api/auth/logout/
Logs the current user out.

## Projects
### GET /api/projects/
Lists projects for the authenticated user.

### POST /api/projects/
Creates a project. The project owner is the logged-in user.

### GET /api/projects/<id>/
Returns project details.

### PUT /api/projects/<id>/
Updates project fields.

## Documents
### POST /api/projects/<id>/documents/
Uploads a file. Supported types: PDF, DOCX, TXT.

### GET /api/projects/<id>/documents/
Lists uploaded documents and metadata.

### POST /api/projects/<id>/process/
Processes unprocessed documents. Response includes `extraction_mode` (`rule_based`, `claude`, `rule_based_fallback`, `mixed`), `ai_errors` (exception class names only), `failed_documents`, and counts.

## Intelligence endpoints
### GET /api/projects/<id>/decisions/
Returns extracted decisions.

### GET /api/projects/<id>/tasks/
Returns project tasks.

### GET /api/projects/<id>/risks/
Returns project risks.

### GET /api/projects/<id>/knowledge-graph/
Returns nodes and edges for a light-weight project graph.

### GET /api/projects/<id>/knowledge-gaps/
Returns detected knowledge gaps and missing facts.

### POST /api/projects/<id>/ask/
Asks a grounded question about the project. Response: `{answer, mode, evidence[]}`. `mode` is `local_keyword_match` (no LLM), `claude` (synthesised from the evidence), or `rule_based_fallback` (Claude failed).

## Handover
### GET /api/projects/<id>/readiness/
Returns the readiness score and category breakdown.

### POST /api/projects/<id>/rehearsals/
Starts a handover rehearsal with a set of project questions.

### POST /api/projects/<id>/handover/
Generates a handover report.

### GET /api/handover/<id>/download/
Downloads the generated report as a text file.

## Notes
This MVP keeps all access project-scoped. The user can only read or edit projects that they own.
