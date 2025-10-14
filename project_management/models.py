from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.core.validators import (
    EmailValidator,
    MinLengthValidator,
    RegexValidator,
    FileExtensionValidator,
    MinValueValidator,
)
from django.db.models import Q, F, Sum
from django.core.exceptions import ValidationError

from professional.models import Professional


@deconstructible
class MaxFileSizeValidator:
    def __init__(self, max_mb: int = 10):
        self.max_mb = max_mb

    def __call__(self, file):
        if file and hasattr(file, "size") and file.size is not None:
            limit_bytes = self.max_mb * 1024 * 1024
            if file.size > limit_bytes:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"File too large. Max size is {self.max_mb} MB.")


def validate_mime_type(file):
    allowed_mimes = {
        "image/png": {".png"},
        "image/jpeg": {".jpg", ".jpeg"},
        "application/pdf": {".pdf"},
        "text/plain": {".txt"},
    }
    content_type = getattr(file, "content_type", None)
    name = getattr(file, "name", "") or ""
    ext = (("." + name.split(".")[-1].lower()) if "." in name else "").lower()
    if content_type and ext:
        matched_exts = allowed_mimes.get(content_type)
        if matched_exts is not None and ext not in matched_exts:
            raise ValidationError(
                f"File type/extension mismatch: '{content_type}' with '{ext}' not allowed."
            )


max_10mb = MaxFileSizeValidator(10)

allowed_extensions = FileExtensionValidator(
    allowed_extensions=["pdf", "jpg", "jpeg", "png", "txt"]
)

PLAN_LIMITS = {
    "free": {
        "pm_enabled": False,
        "max_projects": 0,
        "max_members_per_project": 0,
        "max_active_tasks_per_project": 0,
        "max_storage_mb_per_project": 0,
    },
    "pro": {
        "pm_enabled": True,
        "max_projects": 50,
        "max_members_per_project": 50,
        "max_active_tasks_per_project": 5000,
        "max_storage_mb_per_project": 10240,
    },
    "enterprise": {
        "pm_enabled": True,
        "max_projects": None,
        "max_members_per_project": None,
        "max_active_tasks_per_project": None,
        "max_storage_mb_per_project": None,
    },
}


def _get_user_plan_limits(user):
    now = timezone.now()
    sub = getattr(user, "professional_subscription", None)
    if not sub or not sub.active or (sub.end_date and sub.end_date <= now):
        return PLAN_LIMITS["free"], "free"
    plan_name = (sub.plan.name if sub.plan else "free").lower()
    limits = PLAN_LIMITS.get(plan_name)
    if not limits:
        limits = {
            "pm_enabled": True,
            "max_projects": None,
            "max_members_per_project": None,
            "max_active_tasks_per_project": None,
            "max_storage_mb_per_project": None,
        }
    return limits, plan_name


def _ensure_pm_access(user):
    limits, _ = _get_user_plan_limits(user)
    if not limits.get("pm_enabled", False):
        raise ValidationError("Project management features require a paid plan.")


def _ensure_subscription_allows_project(owner_professional, new_project=False):
    limits, _ = _get_user_plan_limits(owner_professional.user)
    if not limits.get("pm_enabled", False):
        raise ValidationError("Project management features require a paid plan.")
    max_projects = limits.get("max_projects")
    if max_projects is None:
        return
    owned_count = Project.objects.filter(owner=owner_professional).count()
    if new_project:
        owned_count += 1
    if owned_count > max_projects:
        raise ValidationError(f"Plan limit reached: maximum {max_projects} projects.")


def _ensure_subscription_allows_member(project, new_member=False):
    limits, _ = _get_user_plan_limits(project.owner.user)
    if not limits.get("pm_enabled", False):
        raise ValidationError("Project management features require a paid plan.")
    max_members = limits.get("max_members_per_project")
    if max_members is None:
        return
    current = ProjectMember.objects.filter(project=project, is_active=True).count()
    if new_member:
        current += 1
    if current > max_members:
        raise ValidationError(
            f"Plan limit reached: maximum {max_members} active members per project."
        )


def _ensure_subscription_allows_task(project, adding_active=False):
    limits, _ = _get_user_plan_limits(project.owner.user)
    if not limits.get("pm_enabled", False):
        raise ValidationError("Project management features require a paid plan.")
    max_tasks = limits.get("max_active_tasks_per_project")
    if max_tasks is None:
        return
    active_qs = Task.objects.filter(project=project).exclude(status=Task.Status.DONE)
    count = active_qs.count()
    if adding_active:
        count += 1
    if count > max_tasks:
        raise ValidationError(
            f"Plan limit reached: maximum {max_tasks} active tasks per project."
        )


def _project_storage_used_bytes(project):
    agg = TaskAttachment.objects.filter(task__project=project).aggregate(
        total=Sum("file_size")
    )
    return int(agg["total"] or 0)


def _ensure_subscription_allows_storage(project, adding_bytes=0):
    limits, _ = _get_user_plan_limits(project.owner.user)
    if not limits.get("pm_enabled", False):
        raise ValidationError("Project management features require a paid plan.")
    limit_mb = limits.get("max_storage_mb_per_project")
    if limit_mb is None:
        return
    used = _project_storage_used_bytes(project)
    cap_bytes = int(limit_mb * 1024 * 1024)
    if used + int(adding_bytes) > cap_bytes:
        raise ValidationError(f"Plan storage limit reached: {limit_mb} MB per project.")


class Member(models.Model):
    full_name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(2, "Name must be at least 2 characters.")],
    )
    email = models.EmailField(
        max_length=254,
        validators=[EmailValidator()],
        blank=True,
        null=True,
        help_text="Optional; used for notifications.",
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9().\-\s]{6,}$",
                message="Enter a valid phone number.",
            )
        ],
    )
    title = models.CharField(max_length=120, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["email"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="member_contact_email_or_phone",
                check=(
                    (Q(email__isnull=False) & ~Q(email=""))
                    | (Q(phone__isnull=False) & ~Q(phone=""))
                ),
            ),
        ]

    def __str__(self):
        return self.full_name


class Project(models.Model):
    name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3, "Project name must be at least 3 characters.")],
    )
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        Professional,
        on_delete=models.CASCADE,
        related_name="owned_projects",
        help_text="Project owner (a verified Professional).",
    )
    team_members = models.ManyToManyField(
        Member, through="ProjectMember", related_name="projects", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner"])]

    def __str__(self):
        return self.name

    def clean(self):
        if not self.owner_id:
            raise ValidationError("Project owner is required.")
        _ensure_pm_access(self.owner.user)
        _ensure_subscription_allows_project(self.owner, new_project=self.pk is None)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        MANAGER = ("manager", "Manager")
        DEVELOPER = ("developer", "Developer")
        DESIGNER = ("designer", "Designer")
        QA = ("qa", "QA / Tester")
        ANALYST = ("analyst", "Analyst")
        OTHER = ("other", "Other")

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="project_memberships"
    )
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OTHER)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("project", "member")]
        ordering = ["project", "member__full_name"]
        indexes = [
            models.Index(fields=["project", "is_active"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.member.full_name} @ {self.project.name} ({self.role})"

    def clean(self):
        _ensure_pm_access(self.project.owner.user)
        creating = self.pk is None
        if self.is_active:
            _ensure_subscription_allows_member(self.project, new_member=creating)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = ("TODO", "To Do")
        IN_PROGRESS = ("IN_PROGRESS", "In Progress")
        DONE = ("DONE", "Done")

    class Priority(models.TextChoices):
        LOW = ("LOW", "Low")
        MEDIUM = ("MEDIUM", "Medium")
        HIGH = ("HIGH", "High")

    title = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3, "Title must be at least 3 characters.")],
    )
    description = models.TextField(blank=True, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    assignee = models.ForeignKey(
        ProjectMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        help_text="Who is responsible for this task.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        ProjectMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tasks",
    )
    parent_task = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="subtasks")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["due_date"]),
        ]

    def clean(self):
        _ensure_pm_access(self.project.owner.user)
        creating = self.pk is None

        if self.parent_task and self.parent_task_id == self.id:
            raise ValidationError("A task cannot be its own parent.")
        if self.parent_task and self.parent_task.project_id != self.project_id:
            raise ValidationError("Parent task must belong to the same project.")
        p = self.parent_task
        while p:
            if p.id == self.id:
                raise ValidationError("Circular parent-child relationship detected.")
            p = p.parent_task

        if self.assignee and self.assignee.project_id != self.project_id:
            raise ValidationError({"assignee": "Assignee must belong to the same project."})
        if self.created_by and self.created_by.project_id != self.project_id:
            raise ValidationError({"created_by": "Creator must belong to the same project."})

        if self.due_date and self.status in {Task.Status.TODO, Task.Status.IN_PROGRESS}:
            if self.due_date < timezone.now().date():
                raise ValidationError("Due date cannot be in the past for non-done tasks.")

        if creating and self.status != Task.Status.DONE:
            _ensure_subscription_allows_task(self.project, adding_active=True)
        if not creating:
            old = Task.objects.get(pk=self.pk)
            was_active = old.status != Task.Status.DONE
            will_be_active = self.status != Task.Status.DONE
            if not was_active and will_be_active:
                _ensure_subscription_allows_task(self.project, adding_active=True)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


def task_attachment_path(instance, filename):
    return f"task_attachments/{instance.task.project_id}/{instance.task_id}/{filename}"


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        ProjectMember, on_delete=models.SET_NULL, null=True, related_name="task_comments"
    )
    content = models.TextField(
        validators=[MinLengthValidator(1, "Comment cannot be empty.")]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["task", "created_at"])]

    def __str__(self):
        who = self.author.member.full_name if self.author else "unknown"
        return f"Comment by {who} on {self.task.title}"


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to=task_attachment_path,
        validators=[max_10mb, allowed_extensions, validate_mime_type],
        help_text="Max 10MB. Allowed: pdf, jpg, jpeg, png, txt.",
    )
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0, editable=False)
    uploaded_by = models.ForeignKey(
        ProjectMember, on_delete=models.SET_NULL, null=True, related_name="uploaded_task_attachments"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["task", "uploaded_at"]),
            models.Index(fields=["task"]),
        ]

    def __str__(self):
        return f"{self.filename} · {self.task.title}"

    def clean(self):
        _ensure_pm_access(self.task.project.owner.user)
        if self.filename and "." not in self.filename:
            raise ValidationError("Filename must include an extension (e.g., 'doc.pdf').")
        if self.file and self.file.name and self.filename:
            ext1 = self.file.name.split(".")[-1].lower() if "." in self.file.name else ""
            ext2 = self.filename.split(".")[-1].lower() if "." in self.filename else ""
            if ext1 and ext2 and ext1 != ext2:
                raise ValidationError(
                    "Filename extension must match the uploaded file's extension."
                )
        try:
            size_bytes = int(getattr(self.file, "size", 0) or 0)
        except Exception:
            size_bytes = 0
        if self.pk:
            old = TaskAttachment.objects.get(pk=self.pk)
            delta = size_bytes - int(old.file_size or 0)
            _ensure_subscription_allows_storage(self.task.project, adding_bytes=delta)
        else:
            _ensure_subscription_allows_storage(self.task.project, adding_bytes=size_bytes)

    def save(self, *args, **kwargs):
        if not self.filename and self.file and self.file.name:
            self.filename = self.file.name.split("/")[-1]
        try:
            self.file_size = int(getattr(self.file, "size", 0) or 0)
        except Exception:
            self.file_size = 0
        self.clean()
        super().save(*args, **kwargs)
