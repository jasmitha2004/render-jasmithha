from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Project(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='documents')
    filename = models.CharField(max_length=512)
    file_path = models.CharField(max_length=1024)
    file_type = models.CharField(max_length=20)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    page_count = models.IntegerField(default=0)
    char_count = models.IntegerField(default=0)

    def __str__(self):
        return self.filename


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='chunks')
    content = models.TextField()
    page_number = models.IntegerField(default=1)
    chunk_index = models.IntegerField(default=0)

    class Meta:
        ordering = ['document', 'chunk_index']


class Decision(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='decisions')
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    rationale = models.TextField(blank=True)
    decided_by = models.CharField(max_length=255, blank=True)
    decided_at = models.CharField(max_length=100, blank=True)
    source_document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    confidence = models.FloatField(default=0.7)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('blocked', 'Blocked'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    assignee = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.CharField(max_length=100, blank=True)
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependents')
    source_document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', '-created_at']


class Risk(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='risks')
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    mitigation = models.TextField(blank=True)
    owner = models.CharField(max_length=255, blank=True)
    source_document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class KnowledgeGap(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='knowledge_gaps')
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    severity = models.CharField(max_length=20, default='medium')
    suggested_action = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class HandoverReport(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='handover_reports')
    version = models.IntegerField(default=1)
    content = models.TextField()
    readiness_score = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-created_at']


class Employee(models.Model):
    """Stored for future RBAC; not used as login identity in MVP."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='employees')
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
