import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.utils.text import get_valid_filename
from django.http import HttpResponse, FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication

from .models import (
    Project, Document, DocumentChunk, Decision, Task, Risk,
    KnowledgeGap, HandoverReport,
)
from .serializers import (
    RegisterSerializer, UserSerializer, ProjectSerializer, DocumentSerializer,
    DecisionSerializer, TaskSerializer, RiskSerializer, KnowledgeGapSerializer,
    HandoverReportSerializer,
)
from .services.knowledge_services import (
    extract_text_from_file, chunk_text,
    extract_decisions, extract_tasks, extract_risks,
    KnowledgeGapDetector, ReadinessCalculator, answer_question,
    ClaudeExtractionService, extract_knowledge,
)

logger = logging.getLogger('contextbridge.api')


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth without CSRF enforcement.

    Safe here because the API is called server-to-server by the Streamlit process,
    which holds the session cookie itself; a browser never carries it cross-site.
    If the API is ever called directly from browser JavaScript, switch to token
    auth or re-enable CSRF.
    """

    def enforce_csrf(self, request):
        return  # skip CSRF check


def _get_owned_project(request, project_id):
    return get_object_or_404(Project, id=project_id, owner=request.user)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def health(request):
    """Liveness + DB check for Render. Reports AI mode without exposing the key."""
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
        db_ok = True
    except Exception:
        logger.exception('Health check: database unreachable')
        db_ok = False
    body = {
        'status': 'ok' if db_ok else 'degraded',
        'database': 'ok' if db_ok else 'unreachable',
        'ai_mode': 'claude' if ClaudeExtractionService().available else 'rule_based',
    }
    return Response(body, status=200 if db_ok else 503)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    return Response({
        'user': UserSerializer(user).data,
        'detail': 'Logged in',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def logout_view(request):
    logout(request)
    return Response({'detail': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def me(request):
    return Response(UserSerializer(request.user).data)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def project_list_create(request):
    if request.method == 'GET':
        projects = Project.objects.filter(owner=request.user)
        return Response(ProjectSerializer(projects, many=True).data)
    serializer = ProjectSerializer(data=request.data)
    if serializer.is_valid():
        project = serializer.save(owner=request.user)
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def project_detail(request, project_id):
    project = _get_owned_project(request, project_id)
    if request.method == 'GET':
        return Response(ProjectSerializer(project).data)
    if request.method == 'DELETE':
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = ProjectSerializer(project, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def document_list_upload(request, project_id):
    project = _get_owned_project(request, project_id)
    if request.method == 'GET':
        docs = project.documents.all()
        return Response(DocumentSerializer(docs, many=True).data)

    # Upload
    uploaded = request.FILES.get('file')
    if not uploaded:
        return Response({'detail': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    name = get_valid_filename(Path(uploaded.name).name) or 'upload'
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if uploaded.size > max_bytes:
        return Response({'detail': f'File too large (limit {settings.MAX_UPLOAD_MB} MB)'},
                        status=status.HTTP_400_BAD_REQUEST)
    ext = Path(name).suffix.lower().lstrip('.')
    if ext not in ('pdf', 'docx', 'txt', 'doc', 'text'):
        return Response({'detail': 'Supported types: PDF, DOCX, TXT'}, status=status.HTTP_400_BAD_REQUEST)

    media_dir = Path(settings.MEDIA_ROOT) / 'uploads' / str(project.id)
    media_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{name}"
    dest = media_dir / safe_name
    with open(dest, 'wb') as f:
        for chunk in uploaded.chunks():
            f.write(chunk)

    doc = Document.objects.create(
        project=project,
        filename=name,
        file_path=str(dest),
        file_type=ext,
    )
    return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def process_project(request, project_id):
    project = _get_owned_project(request, project_id)
    docs = project.documents.filter(processed=False)
    processed_count = 0

    claude = ClaudeExtractionService()
    modes, errors, failed = set(), [], []

    for doc in docs:
        try:
            text, pages = extract_text_from_file(doc.file_path, doc.file_type)
        except Exception:
            logger.exception('Text extraction failed for document %s', doc.id)
            failed.append(doc.filename)
            continue
        if not text.strip():
            failed.append(doc.filename)
            continue

        doc.page_count = pages
        doc.char_count = len(text)
        doc.processed = True
        doc.save()

        chunks = chunk_text(text)
        DocumentChunk.objects.filter(document=doc).delete()
        for i, content in enumerate(chunks):
            DocumentChunk.objects.create(
                document=doc,
                project=project,
                content=content,
                page_number=min(i // 3 + 1, max(1, pages)),
                chunk_index=i,
            )

        data, mode, err = extract_knowledge(text, claude)
        modes.add(mode)
        if err:
            errors.append(err)
        for d in data['decisions']:
            Decision.objects.create(project=project, source_document=doc, **d)
        for t in data['tasks']:
            Task.objects.create(project=project, source_document=doc, **t)
        for r in data['risks']:
            Risk.objects.create(project=project, source_document=doc, **r)

        processed_count += 1
        logger.info('Processed document %s (mode=%s)', doc.id, mode)

    # Re-detect gaps
    KnowledgeGap.objects.filter(project=project).delete()
    detector = KnowledgeGapDetector()
    for gap in detector.detect(project):
        KnowledgeGap.objects.create(project=project, **gap)

    if len(modes) == 1:
        extraction_mode = next(iter(modes))
    elif modes:
        extraction_mode = 'mixed'
    else:
        extraction_mode = None
    detail = f'Processed {processed_count} document(s)'
    if failed:
        detail += f'; {len(failed)} could not be read: {", ".join(failed)}'
    return Response({
        'detail': detail,
        'extraction_mode': extraction_mode,
        'ai_errors': sorted(set(errors)),
        'failed_documents': failed,
        'decisions': project.decisions.count(),
        'tasks': project.tasks.count(),
        'risks': project.risks.count(),
        'gaps': project.knowledge_gaps.count(),
    })


# ---------------------------------------------------------------------------
# Intelligence endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def decisions_list(request, project_id):
    project = _get_owned_project(request, project_id)
    return Response(DecisionSerializer(project.decisions.all(), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def tasks_list(request, project_id):
    project = _get_owned_project(request, project_id)
    return Response(TaskSerializer(project.tasks.all(), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def risks_list(request, project_id):
    project = _get_owned_project(request, project_id)
    return Response(RiskSerializer(project.risks.all(), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def knowledge_gaps_list(request, project_id):
    project = _get_owned_project(request, project_id)
    return Response(KnowledgeGapSerializer(project.knowledge_gaps.all(), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def knowledge_graph(request, project_id):
    project = _get_owned_project(request, project_id)
    nodes = []
    edges = []

    nodes.append({'id': f'project_{project.id}', 'label': project.name, 'type': 'project'})

    for d in project.decisions.all()[:30]:
        nid = f'decision_{d.id}'
        nodes.append({'id': nid, 'label': d.title[:40], 'type': 'decision'})
        edges.append({'source': f'project_{project.id}', 'target': nid, 'relation': 'has_decision'})

    for t in project.tasks.all()[:30]:
        nid = f'task_{t.id}'
        nodes.append({'id': nid, 'label': t.title[:40], 'type': 'task'})
        edges.append({'source': f'project_{project.id}', 'target': nid, 'relation': 'has_task'})

    for r in project.risks.all()[:20]:
        nid = f'risk_{r.id}'
        nodes.append({'id': nid, 'label': r.title[:40], 'type': 'risk'})
        edges.append({'source': f'project_{project.id}', 'target': nid, 'relation': 'has_risk'})

    return Response({'nodes': nodes, 'edges': edges})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def ask_question(request, project_id):
    project = _get_owned_project(request, project_id)
    question = request.data.get('question', '').strip()
    if not question:
        return Response({'detail': 'question is required'}, status=status.HTTP_400_BAD_REQUEST)
    result = answer_question(project, question)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def readiness(request, project_id):
    project = _get_owned_project(request, project_id)
    calc = ReadinessCalculator()
    return Response(calc.calculate(project))


# ---------------------------------------------------------------------------
# Handover
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def start_rehearsal(request, project_id):
    project = _get_owned_project(request, project_id)
    questions = [
        f"What is the primary goal of {project.name}?",
        "Who owns the critical path tasks?",
        "What are the highest severity open risks?",
        "Which key decisions still lack rationale?",
        "What knowledge gaps must be closed before handover?",
    ]
    return Response({'questions': questions, 'project': project.name})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def generate_handover(request, project_id):
    project = _get_owned_project(request, project_id)
    calc = ReadinessCalculator()
    readiness_data = calc.calculate(project)

    lines = [
        f"# Handover Report — {project.name}",
        f"Generated for: {request.user.username}",
        f"Readiness score: {readiness_data['overall_score']}/100",
        f"Recommendation: {readiness_data['recommendation']}",
        "",
        "## Category scores",
    ]
    for k, v in readiness_data['categories'].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    lines += ["", "## Decisions"]
    for d in project.decisions.all()[:20]:
        lines.append(f"- **{d.title}**")
        if d.rationale:
            lines.append(f"  Rationale: {d.rationale[:200]}")

    lines += ["", "## Tasks"]
    for t in project.tasks.all()[:20]:
        lines.append(f"- [{t.status}] {t.title} (owner: {t.assignee or 'unassigned'})")

    lines += ["", "## Risks"]
    for r in project.risks.all()[:15]:
        lines.append(f"- [{r.severity}] {r.title}")

    lines += ["", "## Knowledge gaps"]
    for g in project.knowledge_gaps.all()[:15]:
        lines.append(f"- {g.title} — {g.suggested_action[:100]}")

    content = "\n".join(lines)
    last = project.handover_reports.order_by('-version').first()
    version = (last.version + 1) if last else 1
    report = HandoverReport.objects.create(
        project=project,
        version=version,
        content=content,
        readiness_score=readiness_data['overall_score'],
        created_by=request.user,
    )
    return Response(HandoverReportSerializer(report).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def download_report(request, report_id):
    report = get_object_or_404(HandoverReport, id=report_id, project__owner=request.user)
    response = HttpResponse(report.content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="handover_v{report.version}.txt"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def list_reports(request, project_id):
    project = _get_owned_project(request, project_id)
    reports = project.handover_reports.all()
    return Response(HandoverReportSerializer(reports, many=True).data)


# ---------------------------------------------------------------------------
# Workspace overview (executive metrics)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def workspace_overview(request):
    projects = Project.objects.filter(owner=request.user)
    total_projects = projects.count()
    total_docs = Document.objects.filter(project__owner=request.user).count()
    total_decisions = Decision.objects.filter(project__owner=request.user).count()
    total_tasks = Task.objects.filter(project__owner=request.user).count()
    total_risks = Risk.objects.filter(project__owner=request.user).count()
    total_gaps = KnowledgeGap.objects.filter(project__owner=request.user).count()

    project_summaries = []
    calc = ReadinessCalculator()
    for p in projects[:10]:
        r = calc.calculate(p)
        project_summaries.append({
            'id': p.id,
            'name': p.name,
            'readiness': r['overall_score'],
            'documents': p.documents.count(),
            'gaps': p.knowledge_gaps.count(),
        })

    return Response({
        'totals': {
            'projects': total_projects,
            'documents': total_docs,
            'decisions': total_decisions,
            'tasks': total_tasks,
            'risks': total_risks,
            'gaps': total_gaps,
        },
        'projects': project_summaries,
    })
