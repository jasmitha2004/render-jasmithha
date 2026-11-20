from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health, name='api-health'),

    # Auth
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me, name='me'),

    # Workspace
    path('workspace/overview/', views.workspace_overview, name='workspace-overview'),

    # Projects
    path('projects/', views.project_list_create, name='project-list'),
    path('projects/<int:project_id>/', views.project_detail, name='project-detail'),

    # Documents
    path('projects/<int:project_id>/documents/', views.document_list_upload, name='documents'),
    path('projects/<int:project_id>/process/', views.process_project, name='process'),

    # Intelligence
    path('projects/<int:project_id>/decisions/', views.decisions_list, name='decisions'),
    path('projects/<int:project_id>/tasks/', views.tasks_list, name='tasks'),
    path('projects/<int:project_id>/risks/', views.risks_list, name='risks'),
    path('projects/<int:project_id>/knowledge-gaps/', views.knowledge_gaps_list, name='gaps'),
    path('projects/<int:project_id>/knowledge-graph/', views.knowledge_graph, name='graph'),
    path('projects/<int:project_id>/ask/', views.ask_question, name='ask'),
    path('projects/<int:project_id>/readiness/', views.readiness, name='readiness'),

    # Handover
    path('projects/<int:project_id>/rehearsals/', views.start_rehearsal, name='rehearsal'),
    path('projects/<int:project_id>/handover/', views.generate_handover, name='handover'),
    path('projects/<int:project_id>/reports/', views.list_reports, name='reports'),
    path('handover/<int:report_id>/download/', views.download_report, name='download-report'),
]
