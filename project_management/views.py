from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Member, Project, ProjectMember, Task, TaskComment, TaskAttachment
from .serializers import (
    MemberSerializer,
    ProjectSerializer,
    ProjectMemberSerializer,
    TaskSerializer,
    TaskCommentSerializer,
    TaskAttachmentSerializer,
)


def _get_professional_or_400(user):
    if not hasattr(user, "professional_profile") or user.professional_profile is None:
        from rest_framework.exceptions import ValidationError
        raise ValidationError("Authenticated professional required.")
    return user.professional_profile


class MemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Member.objects.all().order_by("full_name")
    serializer_class = MemberSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Project.objects.select_related("owner").prefetch_related("team_members", "project_memberships")
    serializer_class = ProjectSerializer

    def get_queryset(self):
        if hasattr(self.request.user, "professional_profile"):
            return self.queryset.filter(owner=self.request.user.professional_profile)
        return self.queryset.none()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        _get_professional_or_400(request.user)
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="add-member")
    @transaction.atomic
    def add_member(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ProjectMember.objects.create(
            project=project,
            member=serializer.validated_data["member"],
            role=serializer.validated_data.get("role") or ProjectMember.Role.OTHER,
            is_active=serializer.validated_data.get("is_active", True),
        )
        return Response({"detail": "Member added."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="remove-member")
    @transaction.atomic
    def remove_member(self, request, pk=None):
        project = self.get_object()
        member_id = request.data.get("member_id")
        if not member_id:
            return Response({"detail": "member_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        ProjectMember.objects.filter(project=project, member_id=member_id).delete()
        return Response({"detail": "Member removed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="members")
    def list_members(self, request, pk=None):
        project = self.get_object()
        qs = ProjectMember.objects.select_related("member").filter(project=project).order_by("member__full_name")
        data = ProjectMemberSerializer(qs, many=True).data
        return Response(data)

    @action(detail=True, methods=["get"], url_path="tasks")
    def list_tasks(self, request, pk=None):
        project = self.get_object()
        qs = Task.objects.select_related("assignee", "created_by").filter(project=project).order_by("-created_at")
        data = TaskSerializer(qs, many=True).data
        return Response(data)


class ProjectMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectMemberSerializer

    def get_queryset(self):
        qs = ProjectMember.objects.select_related("project", "member")
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if hasattr(self.request.user, "professional_profile"):
            qs = qs.filter(project__owner=self.request.user.professional_profile)
        else:
            qs = qs.none()
        return qs.order_by("member__full_name")


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Task.objects.select_related("project", "assignee", "created_by")
    serializer_class = TaskSerializer

    def get_queryset(self):
        qs = self.queryset
        if hasattr(self.request.user, "professional_profile"):
            qs = qs.filter(project__owner=self.request.user.professional_profile)
        else:
            return self.queryset.none()

        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)

        status_value = self.request.query_params.get("status")
        if status_value:
            qs = qs.filter(status=status_value)

        assignee_pm = self.request.query_params.get("assignee")
        if assignee_pm:
            qs = qs.filter(assignee_id=assignee_pm)

        parent_task = self.request.query_params.get("parent")
        if parent_task:
            qs = qs.filter(parent_task_id=parent_task)

        return qs.order_by("-created_at")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="assign")
    @transaction.atomic
    def assign(self, request, pk=None):
        task = self.get_object()
        pm_id = request.data.get("project_member_id")
        if not pm_id:
            return Response({"detail": "project_member_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        assignee = get_object_or_404(ProjectMember, pk=pm_id)
        if assignee.project_id != task.project_id:
            return Response({"detail": "Assignee must be a member of the same project."}, status=400)
        task.assignee = assignee
        task.full_clean()
        task.save(update_fields=["assignee", "updated_at"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="set-status")
    @transaction.atomic
    def set_status(self, request, pk=None):
        task = self.get_object()
        status_value = request.data.get("status")
        if status_value not in Task.Status.values:
            return Response({"detail": "Invalid status."}, status=400)
        task.status = status_value
        task.full_clean()
        task.save(update_fields=["status", "updated_at"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="members")
    def task_members(self, request, pk=None):
        task = self.get_object()
        qs = ProjectMember.objects.select_related("member").filter(project=task.project).order_by("member__full_name")
        return Response(ProjectMemberSerializer(qs, many=True).data)


class TaskCommentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = TaskComment.objects.select_related("task", "author")
    serializer_class = TaskCommentSerializer

    def get_queryset(self):
        qs = self.queryset
        if hasattr(self.request.user, "professional_profile"):
            qs = qs.filter(task__project__owner=self.request.user.professional_profile)
        else:
            return self.queryset.none()

        task_id = self.request.query_params.get("task")
        if task_id:
            qs = qs.filter(task_id=task_id)

        return qs.order_by("created_at")


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = TaskAttachment.objects.select_related("task", "uploaded_by")
    serializer_class = TaskAttachmentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = self.queryset
        if hasattr(self.request.user, "professional_profile"):
            qs = qs.filter(task__project__owner=self.request.user.professional_profile)
        else:
            return self.queryset.none()

        task_id = self.request.query_params.get("task")
        if task_id:
            qs = qs.filter(task_id=task_id)

        return qs.order_by("-uploaded_at")
