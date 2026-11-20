from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Project, Document, Decision, Task, Risk, KnowledgeGap, HandoverReport, Employee
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return user


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    document_count = serializers.SerializerMethodField()
    decision_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()
    risk_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            'id', 'name', 'description', 'owner', 'created_at', 'updated_at',
            'document_count', 'decision_count', 'task_count', 'risk_count',
        )
        read_only_fields = ('owner', 'created_at', 'updated_at')

    def get_document_count(self, obj):
        return obj.documents.count()

    def get_decision_count(self, obj):
        return obj.decisions.count()

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_risk_count(self, obj):
        return obj.risks.count()


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            'id', 'filename', 'file_type', 'uploaded_at', 'processed',
            'page_count', 'char_count',
        )
        read_only_fields = fields


class DecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = (
            'id', 'title', 'description', 'rationale', 'decided_by',
            'decided_at', 'confidence', 'created_at',
        )


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            'id', 'title', 'description', 'assignee', 'status',
            'due_date', 'created_at',
        )


class RiskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Risk
        fields = (
            'id', 'title', 'description', 'severity', 'mitigation',
            'owner', 'created_at',
        )


class KnowledgeGapSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeGap
        fields = (
            'id', 'title', 'description', 'category', 'severity',
            'suggested_action', 'created_at',
        )


class HandoverReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverReport
        fields = ('id', 'version', 'content', 'readiness_score', 'created_at')
