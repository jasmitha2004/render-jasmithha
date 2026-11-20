"""
Create demo user + Nexora / Apollo sample project with synthetic knowledge.
Run from repo root: python backend/sample_data_generator.py
"""
import os
import sys
import django
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'contextbridge.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from contextbridge_app.models import (
    Project, Decision, Task, Risk, KnowledgeGap, Document, DocumentChunk,
)


DEMO_PASSWORD = os.getenv('DEMO_PASSWORD', 'DemoPass123')


def main():
    user, created = User.objects.get_or_create(
        username='demo',
        defaults={'email': 'demo@nexora.example'},
    )
    if created:
        user.set_password(DEMO_PASSWORD)
        user.save()
        print('Created user: demo (password from DEMO_PASSWORD or the documented default)')
    else:
        print('User demo already exists')

    project, _ = Project.objects.get_or_create(
        owner=user,
        name='Apollo Enterprise Platform',
        defaults={
            'description': (
                'Migration and modernization of the Apollo customer platform. '
                'Includes database strategy, ownership of critical services, and handover readiness.'
            ),
        },
    )

    # Clear previous demo entities for idempotency
    Decision.objects.filter(project=project).delete()
    Task.objects.filter(project=project).delete()
    Risk.objects.filter(project=project).delete()
    KnowledgeGap.objects.filter(project=project).delete()

    Decision.objects.create(
        project=project,
        title='Use MongoDB for primary document store',
        description='Selected MongoDB for flexible schema on product catalog and customer profiles.',
        rationale='Rapid product iteration required schema flexibility that relational tables constrained.',
        decided_by='Architecture Review Board',
        decided_at='2025-Q3 planning',
        confidence=0.9,
    )
    Decision.objects.create(
        project=project,
        title='Adopt event-driven architecture for order pipeline',
        description='Kafka-based events between order, inventory, and fulfillment services.',
        rationale='Decouple services and support peak load during campaigns.',
        decided_by='Platform lead',
        decided_at='Sprint 12',
        confidence=0.85,
    )
    Decision.objects.create(
        project=project,
        title='Evaluate PostgreSQL for financial ledger',
        description='ACID requirements for billing may require a secondary PostgreSQL store.',
        rationale='MongoDB alone may not satisfy strict consistency for money movement.',
        decided_by='Finance eng + architecture',
        decided_at='Open',
        confidence=0.7,
    )

    Task.objects.create(
        project=project,
        title='Complete MongoDB → dual-write pilot',
        description='Run dual-write for catalog for 2 weeks and compare consistency.',
        assignee='Priya N.',
        status='in_progress',
        due_date='2026-01-15',
    )
    Task.objects.create(
        project=project,
        title='Document ownership matrix for fulfillment services',
        description='Map each microservice to on-call owner and backup.',
        assignee='',
        status='pending',
    )
    Task.objects.create(
        project=project,
        title='Close security review for Kafka ACLs',
        description='Security team sign-off on topic ACLs and mTLS.',
        assignee='Security team',
        status='blocked',
        due_date='2026-02-01',
    )
    Task.objects.create(
        project=project,
        title='Write runbooks for order replay',
        description='Operational runbooks for replaying failed order events.',
        assignee='Ops',
        status='pending',
    )

    Risk.objects.create(
        project=project,
        title='Single-region MongoDB deployment',
        description='Primary cluster is single-region; regional outage would block writes.',
        severity='high',
        mitigation='Multi-region replica set planned for Q1.',
        owner='Infra',
    )
    Risk.objects.create(
        project=project,
        title='Incomplete knowledge of legacy billing rules',
        description='Original authors of billing edge cases have left the company.',
        severity='critical',
        mitigation='',
        owner='',
    )
    Risk.objects.create(
        project=project,
        title='Kafka consumer lag during peak sales',
        description='Observed lag spikes above SLO during Black Friday simulation.',
        severity='medium',
        mitigation='Autoscale consumers and increase partitions.',
        owner='Platform',
    )

    KnowledgeGap.objects.create(
        project=project,
        title='Conflicting database technology decisions',
        description='Both MongoDB and PostgreSQL appear as selected technologies. Clarify which is authoritative for which domain.',
        category='conflicting_decision',
        severity='critical',
        suggested_action='Resolve architecture decision and update documentation.',
    )
    KnowledgeGap.objects.create(
        project=project,
        title='Unassigned task: Document ownership matrix',
        description='Task has no clear owner.',
        category='ownership',
        severity='high',
        suggested_action='Assign an owner before handover.',
    )
    KnowledgeGap.objects.create(
        project=project,
        title='No mitigation for critical risk: Incomplete knowledge of legacy billing rules',
        description='High-severity risk lacks a documented mitigation plan.',
        category='risk',
        severity='high',
        suggested_action='Interview remaining SMEs and capture edge-case rules.',
    )

    # Synthetic document + chunks for Q&A demo
    media = Path(settings.MEDIA_ROOT) / 'uploads' / str(project.id)
    media.mkdir(parents=True, exist_ok=True)
    sample_path = media / 'apollo_sprint_notes.txt'
    sample_text = """
Apollo Enterprise Platform — Sprint Notes

Decision: We decided to use MongoDB for the primary document store to support flexible product schemas.
Rationale: Rapid product iteration required schema flexibility.

Decision: Adopt event-driven architecture for the order pipeline using Kafka.

Task: Complete MongoDB dual-write pilot — assignee Priya N., due 2026-01-15.
Task: Document ownership matrix for fulfillment services — still unassigned.
Task: Close security review for Kafka ACLs — blocked on Security team.

Risk: Single-region MongoDB deployment is a high risk; multi-region planned for Q1.
Risk: Incomplete knowledge of legacy billing rules is critical — original authors have left.
Risk: Kafka consumer lag during peak sales is medium severity.

Open questions: Which system of record owns customer balance after the ledger migration?
Who is the backup owner for the fulfillment orchestrator?
"""
    sample_path.write_text(sample_text.strip(), encoding='utf-8')

    doc, _ = Document.objects.get_or_create(
        project=project,
        filename='apollo_sprint_notes.txt',
        defaults={
            'file_path': str(sample_path),
            'file_type': 'txt',
            'processed': True,
            'page_count': 1,
            'char_count': len(sample_text),
        },
    )
    DocumentChunk.objects.filter(document=doc).delete()
    for i, para in enumerate(sample_text.strip().split('\n\n')):
        if para.strip():
            DocumentChunk.objects.create(
                document=doc,
                project=project,
                content=para.strip(),
                page_number=1,
                chunk_index=i,
            )

    print(f'Project ready: {project.name} (id={project.id})')
    print('Login with user: demo')


if __name__ == '__main__':
    main()
