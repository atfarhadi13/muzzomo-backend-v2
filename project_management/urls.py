from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MemberViewSet,
    ProjectViewSet,
    ProjectMemberViewSet,
    TaskViewSet,
    TaskCommentViewSet,
    TaskAttachmentViewSet,
)

router = DefaultRouter()
router.register(r"members", MemberViewSet, basename="member")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"project-members", ProjectMemberViewSet, basename="project-member")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"task-comments", TaskCommentViewSet, basename="task-comment")
router.register(r"task-attachments", TaskAttachmentViewSet, basename="task-attachment")

urlpatterns = [
    path("", include(router.urls)),
]
