from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Member, Project, ProjectMember, Task, TaskComment, TaskAttachment


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    autocomplete_fields = ("member",)
    fields = ("member", "role", "is_active", "joined_at")
    readonly_fields = ("joined_at",)
    ordering = ("member__full_name",)


class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0
    fields = ("author", "content", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)
    ordering = ("created_at",)


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    fields = ("filename", "file", "file_size", "uploaded_by", "uploaded_at")
    readonly_fields = ("file_size", "uploaded_at")
    autocomplete_fields = ("uploaded_by",)
    ordering = ("-uploaded_at",)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "title")
    search_fields = ("full_name", "email", "phone", "title")
    list_filter = ("title",)
    ordering = ("full_name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner_email", "members_count", "tasks_count", "created_at")
    search_fields = ("name", "description", "owner__user__email")
    list_filter = ("created_at",)
    autocomplete_fields = ("owner",)
    inlines = [ProjectMemberInline]
    date_hierarchy = "created_at"
    list_select_related = ("owner", "owner__user")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("owner__user")
            .annotate(
                members_c=Count("team_members", distinct=True),
                tasks_c=Count("tasks", distinct=True),
            )
        )
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(owner=prof)
        return qs.none()

    @admin.display(description="Owner")
    def owner_email(self, obj):
        return obj.owner.user.email

    @admin.display(description="Members")
    def members_count(self, obj):
        return getattr(obj, "members_c", obj.team_members.count())

    @admin.display(description="Tasks")
    def tasks_count(self, obj):
        return getattr(obj, "tasks_c", obj.tasks.count())


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("member_name", "project_name", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active", "project")
    search_fields = ("member__full_name", "project__name")
    autocomplete_fields = ("project", "member")
    list_select_related = ("project", "member")
    ordering = ("project__name", "member__full_name")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "project__owner__user", "member", "project"
        )
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(project__owner=prof)
        return qs.none()

    @admin.display(description="Member")
    def member_name(self, obj):
        return obj.member.full_name

    @admin.display(description="Project")
    def project_name(self, obj):
        return obj.project.name


@admin.action(description="Mark selected tasks as To Do")
def make_todo(modeladmin, request, queryset):
    queryset.update(status=Task.Status.TODO)


@admin.action(description="Mark selected tasks as In Progress")
def make_in_progress(modeladmin, request, queryset):
    queryset.update(status=Task.Status.IN_PROGRESS)


@admin.action(description="Mark selected tasks as Done")
def make_done(modeladmin, request, queryset):
    queryset.update(status=Task.Status.DONE)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "project_name",
        "assignee_display",
        "status",
        "priority",
        "due_date",
        "is_overdue_display",
        "comments_count_display",
        "attachments_count_display",
        "created_at",
    )
    list_filter = ("status", "priority", "project", "due_date", "created_at")
    search_fields = ("title", "description", "project__name", "assignee__member__full_name")
    autocomplete_fields = ("project", "assignee", "created_by", "parent_task")
    readonly_fields = (
        "created_at",
        "updated_at",
        "is_overdue_display",
        "comments_count_display",
        "attachments_count_display",
    )
    inlines = [TaskCommentInline, TaskAttachmentInline]
    date_hierarchy = "created_at"
    list_select_related = ("project", "project__owner__user", "assignee", "assignee__member")
    actions = (make_todo, make_in_progress, make_done)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "project__owner__user", "assignee", "assignee__member"
        )
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(project__owner=prof)
        return qs.none()

    @admin.display(description="Project")
    def project_name(self, obj):
        return obj.project.name

    @admin.display(description="Assignee")
    def assignee_display(self, obj):
        return obj.assignee.member.full_name if obj.assignee_id else "-"

    @admin.display(boolean=True, description="Overdue")
    def is_overdue_display(self, obj):
        return obj.is_overdue

    @admin.display(description="Comments")
    def comments_count_display(self, obj):
        return obj.comments.count()

    @admin.display(description="Attachments")
    def attachments_count_display(self, obj):
        return obj.attachments.count()


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ("task_title", "author_name", "created_at", "short_content")
    list_filter = ("created_at", "task__project")
    search_fields = ("task__title", "author__member__full_name", "content")
    autocomplete_fields = ("task", "author")
    list_select_related = (
        "task",
        "task__project",
        "task__project__owner__user",
        "author",
        "author__member",
    )
    ordering = ("created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "task__project__owner__user", "author", "author__member"
        )
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(task__project__owner=prof)
        return qs.none()

    @admin.display(description="Task")
    def task_title(self, obj):
        return obj.task.title

    @admin.display(description="Author")
    def author_name(self, obj):
        return obj.author.member.full_name if obj.author_id else "-"

    @admin.display(description="Content")
    def short_content(self, obj):
        txt = (obj.content or "").strip()
        return txt if len(txt) <= 80 else f"{txt[:77]}..."


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "task_title",
        "filename",
        "file_link",
        "file_size_kb",
        "uploaded_by_name",
        "uploaded_at",
    )
    list_filter = ("uploaded_at", "task__project")
    search_fields = ("task__title", "filename", "uploaded_by__member__full_name")
    autocomplete_fields = ("task", "uploaded_by")
    readonly_fields = ("file_size", "uploaded_at")
    list_select_related = (
        "task",
        "task__project",
        "task__project__owner__user",
        "uploaded_by",
        "uploaded_by__member",
    )
    ordering = ("-uploaded_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "task__project__owner__user", "uploaded_by", "uploaded_by__member"
        )
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(task__project__owner=prof)
        return qs.none()

    @admin.display(description="Task")
    def task_title(self, obj):
        return obj.task.title

    @admin.display(description="File")
    def file_link(self, obj):
        if not obj.file:
            return "-"
        return format_html('<a href="{}" target="_blank">open</a>', obj.file.url)

    @admin.display(description="Size (KB)")
    def file_size_kb(self, obj):
        try:
            return round((obj.file_size or 0) / 1024, 1)
        except Exception:
            return 0.0

    @admin.display(description="Uploaded By")
    def uploaded_by_name(self, obj):
        return obj.uploaded_by.member.full_name if obj.uploaded_by_id else "-"