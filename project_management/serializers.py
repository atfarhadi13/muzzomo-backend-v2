from typing import List
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers

from .models import (
    Member,
    Project,
    ProjectMember,
    Task,
    TaskComment,
    TaskAttachment,
)


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "full_name", "email", "phone", "title", "notes"]
        read_only_fields = ["id"]


class ProjectMemberSerializer(serializers.ModelSerializer):
    member = MemberSerializer(read_only=True)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=Member.objects.all(), write_only=True, source="member"
    )

    class Meta:
        model = ProjectMember
        fields = ["id", "project", "member", "member_id", "role", "is_active", "joined_at"]
        read_only_fields = ["id", "joined_at", "project"]


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    team_members = MemberSerializer(many=True, read_only=True)
    team_member_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Member.objects.all(), write_only=True, required=False
    )
    members_count = serializers.IntegerField(source="project_memberships.count", read_only=True)
    tasks_count = serializers.IntegerField(source="tasks.count", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id", "name", "description", "owner",
            "team_members", "team_member_ids",
            "members_count", "tasks_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "team_members", "members_count", "tasks_count", "created_at", "updated_at"]

    @transaction.atomic
    def create(self, validated_data):
        member_ids: List[Member] = validated_data.pop("team_member_ids", [])
        request = self.context.get("request")
        if not request or not hasattr(request.user, "professional_profile"):
            raise serializers.ValidationError("Authenticated professional required.")
        owner_prof = request.user.professional_profile
        project = Project.objects.create(owner=owner_prof, **validated_data)
        if member_ids:
            for m in member_ids:
                ProjectMember.objects.create(project=project, member=m)
        return project

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("team_member_ids", None)
        return super().update(instance, validated_data)


class TaskSerializer(serializers.ModelSerializer):
    assignee = ProjectMemberSerializer(read_only=True)
    assignee_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectMember.objects.all(), write_only=True, required=False, allow_null=True, source="assignee"
    )
    created_by = ProjectMemberSerializer(read_only=True)
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectMember.objects.all(), write_only=True, required=False, allow_null=True, source="created_by"
    )

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "project",
            "assignee", "assignee_id",
            "status", "priority", "due_date",
            "created_at", "updated_at",
            "created_by", "created_by_id",
            "parent_task",
            "is_overdue", "comments_count", "attachments_count",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "assignee", "created_by",
            "is_overdue", "comments_count", "attachments_count",
        ]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        assignee = attrs.get("assignee")
        created_by = attrs.get("created_by")

        if assignee and assignee.project_id != project.id:
            raise serializers.ValidationError("Assignee must be a member of the same project.")
        if created_by and created_by.project_id != project.id:
            raise serializers.ValidationError("Creator must be a member of the same project.")

        status = attrs.get("status") or getattr(self.instance, "status", Task.Status.TODO)
        due_date = attrs.get("due_date") or getattr(self.instance, "due_date", None)
        if due_date and status in {Task.Status.TODO, Task.Status.IN_PROGRESS} and due_date < timezone.now().date():
            raise serializers.ValidationError("Due date cannot be in the past for non-done tasks.")
        return attrs


class TaskCommentSerializer(serializers.ModelSerializer):
    author = ProjectMemberSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectMember.objects.all(), write_only=True, source="author"
    )

    class Meta:
        model = TaskComment
        fields = ["id", "task", "author", "author_id", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def validate(self, attrs):
        task = attrs.get("task") or getattr(self.instance, "task", None)
        author = attrs.get("author")
        if author and task and author.project_id != task.project_id:
            raise serializers.ValidationError("Author must be a member of the task's project.")
        return attrs


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = ProjectMemberSerializer(read_only=True)
    uploaded_by_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectMember.objects.all(), write_only=True, source="uploaded_by"
    )

    class Meta:
        model = TaskAttachment
        fields = ["id", "task", "file", "filename", "file_size", "uploaded_by", "uploaded_by_id", "uploaded_at"]
        read_only_fields = ["id", "file_size", "uploaded_by", "uploaded_at"]

    def validate(self, attrs):
        task = attrs.get("task") or getattr(self.instance, "task", None)
        uploaded_by = attrs.get("uploaded_by")
        if uploaded_by and task and uploaded_by.project_id != task.project_id:
            raise serializers.ValidationError("Uploader must be a member of the task's project.")
        return attrs
