from django.contrib import admin
from .models import (
    Project, Document, DocumentChunk, Decision, Task, Risk,
    KnowledgeGap, HandoverReport, Employee,
)

admin.site.register(Project)
admin.site.register(Document)
admin.site.register(DocumentChunk)
admin.site.register(Decision)
admin.site.register(Task)
admin.site.register(Risk)
admin.site.register(KnowledgeGap)
admin.site.register(HandoverReport)
admin.site.register(Employee)
