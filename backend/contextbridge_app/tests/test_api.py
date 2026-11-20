import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from contextbridge_app.models import Project


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    u = User.objects.create_user(username='tester', password='TestPass123', email='t@example.com')
    return u


@pytest.fixture
def auth_client(client, user):
    client.login(username='tester', password='TestPass123')
    return client


@pytest.fixture
def project(user):
    return Project.objects.create(owner=user, name='Test Project', description='desc')


def test_register(client, db):
    r = client.post('/api/auth/register/', {
        'username': 'newuser',
        'email': 'n@example.com',
        'password': 'StrongPass123',
    }, format='json')
    assert r.status_code == 201
    assert r.data['username'] == 'newuser'


def test_login_logout(client, user):
    r = client.post('/api/auth/login/', {'username': 'tester', 'password': 'TestPass123'}, format='json')
    assert r.status_code == 200
    r2 = client.post('/api/auth/logout/')
    assert r2.status_code == 200


def test_project_owner_isolation(auth_client, project, db):
    other = User.objects.create_user(username='other', password='OtherPass123')
    other_proj = Project.objects.create(owner=other, name='Secret')
    r = auth_client.get(f'/api/projects/{other_proj.id}/')
    assert r.status_code == 404  # get_object_or_404 with owner filter


def test_create_project(auth_client):
    r = auth_client.post('/api/projects/', {'name': 'New', 'description': 'd'}, format='json')
    assert r.status_code == 201
    assert r.data['name'] == 'New'


def test_readiness(auth_client, project):
    r = auth_client.get(f'/api/projects/{project.id}/readiness/')
    assert r.status_code == 200
    assert 'overall_score' in r.data
    assert 'categories' in r.data


def test_ask_empty(auth_client, project):
    r = auth_client.post(f'/api/projects/{project.id}/ask/', {'question': ''}, format='json')
    assert r.status_code == 400


def test_workspace_overview(auth_client, project):
    r = auth_client.get('/api/workspace/overview/')
    assert r.status_code == 200
    assert 'totals' in r.data


# ---------------------------------------------------------------------------
# Production-readiness / AI-honesty tests
# ---------------------------------------------------------------------------
from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from contextbridge_app.services import knowledge_services as ks

SAMPLE = (
    "Decision: We decided to use PostgreSQL for the billing ledger store.\n"
    "Task: Complete the migration runbook for the order service.\n"
    "Risk: Single region deployment could cause a critical outage.\n"
)


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.ANTHROPIC_API_KEY = ''


def _upload(client, project, name='notes.txt', content=SAMPLE):
    return client.post(f'/api/projects/{project.id}/documents/',
                       {'file': SimpleUploadedFile(name, content.encode())}, format='multipart')


def test_health_endpoints_public(client, db):
    for url in ('/health/', '/api/health/'):
        r = client.get(url)
        assert r.status_code == 200
        assert r.json()['status'] == 'ok'
        assert r.json()['ai_mode'] == 'rule_based'


def test_unauthenticated_projects_rejected(client, db):
    assert client.get('/api/projects/').status_code in (401, 403)


def test_upload_rejects_bad_type(auth_client, project):
    r = _upload(auth_client, project, name='evil.exe')
    assert r.status_code == 400


def test_upload_sanitises_filename(auth_client, project, settings):
    r = _upload(auth_client, project, name='../../etc/passwd.txt')
    assert r.status_code == 201
    stored = list(settings.MEDIA_ROOT.rglob('*passwd.txt'))
    assert stored and all(str(settings.MEDIA_ROOT) in str(p) for p in stored)


def test_process_rule_based_reports_honest_mode(auth_client, project):
    _upload(auth_client, project)
    r = auth_client.post(f'/api/projects/{project.id}/process/')
    assert r.status_code == 200
    assert r.data['extraction_mode'] == 'rule_based'
    assert r.data['decisions'] >= 1 and r.data['tasks'] >= 1 and r.data['risks'] >= 1


def test_no_fabricated_decisions():
    """Text that merely mentions a database must not yield invented decisions."""
    assert ks.extract_decisions('We talked about mongodb for a while today.') == []


def test_claude_failure_falls_back_and_says_so(auth_client, project, settings):
    settings.ANTHROPIC_API_KEY = 'sk-test-not-real'
    _upload(auth_client, project)
    with mock.patch.object(ks.ClaudeExtractionService, '_complete', side_effect=RuntimeError('boom')):
        r = auth_client.post(f'/api/projects/{project.id}/process/')
    assert r.status_code == 200
    assert r.data['extraction_mode'] == 'rule_based_fallback'
    assert r.data['ai_errors'] == ['RuntimeError']
    assert r.data['decisions'] >= 1


def test_claude_success_path_is_validated(auth_client, project, settings):
    settings.ANTHROPIC_API_KEY = 'sk-test-not-real'
    _upload(auth_client, project)
    payload = ('{"decisions":[{"title":"Adopt Kafka","rationale":"scale"}],'
               '"tasks":[{"title":"Write runbook","status":"bogus"}],'
               '"risks":[{"title":"Outage","severity":"extreme"}]}')
    with mock.patch.object(ks.ClaudeExtractionService, '_complete', return_value=payload):
        r = auth_client.post(f'/api/projects/{project.id}/process/')
    assert r.data['extraction_mode'] == 'claude'
    assert project.tasks.get().status == 'pending'      # invalid status coerced
    assert project.risks.get().severity == 'medium'     # invalid severity coerced


def test_ask_returns_evidence_and_local_mode(auth_client, project):
    _upload(auth_client, project)
    auth_client.post(f'/api/projects/{project.id}/process/')
    r = auth_client.post(f'/api/projects/{project.id}/ask/', {'question': 'Which database for billing?'}, format='json')
    assert r.status_code == 200
    assert r.data['mode'] == 'local_keyword_match'
    assert r.data['evidence']


def test_handover_versions_and_download(auth_client, project):
    r1 = auth_client.post(f'/api/projects/{project.id}/handover/', {}, format='json')
    r2 = auth_client.post(f'/api/projects/{project.id}/handover/', {}, format='json')
    assert (r1.data['version'], r2.data['version']) == (1, 2)
    d = auth_client.get(f"/api/handover/{r2.data['id']}/download/")
    assert d.status_code == 200 and b'Handover Report' in d.content


def test_conflicting_tech_gap_generalised(auth_client, project):
    from contextbridge_app.models import Decision
    Decision.objects.create(project=project, title='Use Kafka for events', rationale='x')
    Decision.objects.create(project=project, title='Use RabbitMQ for events', rationale='x')
    gaps = ks.KnowledgeGapDetector().detect(project)
    assert any(g['category'] == 'conflicting_decision' for g in gaps)
