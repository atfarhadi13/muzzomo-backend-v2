from django.contrib import admin
from django.utils.html import format_html

from .models import InventoryItem, ItemLocation, InventoryLog


class ItemLocationInline(admin.TabularInline):
    model = ItemLocation
    extra = 0
    fields = ("location_name", "on_hand", "in_use", "updated_at")
    readonly_fields = ("updated_at",)
    autocomplete_fields = ("item",)
    ordering = ("location_name",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "professional",
        "item_type",
        "unit",
        "total_quantity",
        "in_use_quantity",
        "available_qty_display",
        "reorder_point",
        "created_at",
        "updated_at",
    )
    list_filter = ("item_type", "professional")
    search_fields = ("name", "professional__user__email")
    autocomplete_fields = ("professional",)
    readonly_fields = ("created_at", "updated_at", "available_quantity")
    ordering = ("name",)
    inlines = [ItemLocationInline]
    fieldsets = (
        (
            "Item",
            {
                "fields": (
                    "professional",
                    "name",
                    ("item_type", "unit"),
                    ("total_quantity", "in_use_quantity", "available_quantity"),
                    "reorder_point",
                    "notes",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="Available")
    def available_qty_display(self, obj):
        return obj.available_quantity

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("professional__user")
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(professional=prof)
        return qs.none()


@admin.register(ItemLocation)
class ItemLocationAdmin(admin.ModelAdmin):
    list_display = ("item", "location_name", "professional", "on_hand", "in_use", "updated_at")
    list_filter = ("professional",)
    search_fields = ("item__name", "location_name", "professional__user__email")
    autocomplete_fields = ("professional", "item")
    readonly_fields = ("updated_at",)
    ordering = ("item__name", "location_name")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("item", "professional__user")
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(professional=prof)
        return qs.none()


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "professional", "item", "action", "quantity", "unit", "task_link", "note")
    list_filter = ("action", "professional")
    search_fields = ("item__name", "professional__user__email", "note")
    autocomplete_fields = ("professional", "item", "task")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("item", "professional__user", "task", "task__project")
        if request.user.is_superuser:
            return qs
        prof = getattr(request.user, "professional_profile", None)
        if prof:
            return qs.filter(professional=prof)
        return qs.none()

    @admin.display(description="Task")
    def task_link(self, obj):
        if not obj.task_id:
            return "-"
        return format_html(f'<a href="/admin/project_management/task/{obj.task_id}/change/" target="_blank">#{obj.task_id}</a>')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser