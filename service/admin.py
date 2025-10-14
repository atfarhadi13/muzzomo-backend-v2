from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg

from .models import (
    ServiceCategory,
    Unit,
    Service,
    ServiceType,
    ServicePhoto,
    ServiceTypePhoto,
    Rating,
)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "photo_thumb", "description_preview", "services_count", "created_at")
    search_fields = ("title", "description")
    ordering = ("title",)
    readonly_fields = ("created_at", "photo_preview")
    fieldsets = (
        (None, {"fields": ("title", "photo", "photo_preview", "description")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("services")

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="height:24px;width:auto;border-radius:4px;" />', obj.photo.url)
        return "-"
    photo_thumb.short_description = "Photo"

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height:120px;width:auto;border:1px solid #eee;border-radius:6px;padding:4px;" />', obj.photo.url)
        return "-"
    photo_preview.short_description = "Preview"

    def description_preview(self, obj):
        if obj.description:
            return (obj.description[:50] + "…") if len(obj.description) > 50 else obj.description
        return "-"
    description_preview.short_description = "Description"

    def services_count(self, obj):
        return obj.services.count()
    services_count.short_description = "Services"


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "services_count", "created_at")
    search_fields = ("name", "code")
    ordering = ("name",)
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("name", "code")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("services")

    def services_count(self, obj):
        return obj.services.count()
    services_count.short_description = "Services"


class ServicePhotoInline(admin.TabularInline):
    model = ServicePhoto
    extra = 0
    readonly_fields = ("uploaded_at",)
    fields = ("photo", "caption", "uploaded_at")


class ServiceTypeInline(admin.TabularInline):
    model = ServiceType
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("title", "description", "price", "created_at")
    show_change_link = True


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 0
    readonly_fields = ("user", "rating", "review", "created_at")
    fields = ("user", "rating", "review", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "price",
        "unit",
        "is_trade_required",
        "categories_display",
        "average_rating_display",
        "types_count",
        "created_at",
    )
    list_filter = ("is_trade_required", "categories", "unit", "created_at")
    search_fields = ("title", "description")
    filter_horizontal = ("categories",)
    ordering = ("title",)
    readonly_fields = ("created_at", "average_rating_display")
    inlines = [ServiceTypeInline, ServicePhotoInline, RatingInline]
    autocomplete_fields = ("unit",)

    fieldsets = (
        (None, {"fields": ("title", "description")}),
        ("Pricing & Requirements", {"fields": ("price", "unit", "is_trade_required")}),
        ("Categories", {"fields": ("categories",)}),
        ("Statistics", {"fields": ("average_rating_display",)}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("unit").prefetch_related("categories", "types")

    def categories_display(self, obj):
        names = [c.title for c in obj.categories.all()[:3]]
        more = obj.categories.count() - len(names)
        return ", ".join(names) + (f" (+{more})" if more > 0 else "")
    categories_display.short_description = "Categories"

    def average_rating_display(self, obj):
        avg = obj.average_rating
        if avg:
            return format_html("{} {}", avg, "⭐" * int(round(avg)))
        return "No ratings"
    average_rating_display.short_description = "Avg Rating"

    def types_count(self, obj):
        return obj.types.count()
    types_count.short_description = "Types"


class ServiceTypePhotoInline(admin.TabularInline):
    model = ServiceTypePhoto
    extra = 0
    readonly_fields = ("uploaded_at",)
    fields = ("photo", "caption", "uploaded_at")


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "price", "description_preview", "photos_count", "created_at")
    list_filter = ("service", "created_at")
    search_fields = ("title", "description", "service__title")
    ordering = ("service", "title")
    readonly_fields = ("created_at",)
    inlines = [ServiceTypePhotoInline]
    autocomplete_fields = ("service",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("service").prefetch_related("photos")

    def description_preview(self, obj):
        if obj.description:
            return (obj.description[:50] + "…") if len(obj.description) > 50 else obj.description
        return "-"
    description_preview.short_description = "Description"

    def photos_count(self, obj):
        return obj.photos.count()
    photos_count.short_description = "Photos"


@admin.register(ServicePhoto)
class ServicePhotoAdmin(admin.ModelAdmin):
    list_display = ("service", "caption", "photo_preview", "uploaded_at")
    list_filter = ("service", "uploaded_at")
    search_fields = ("service__title", "caption")
    ordering = ("-uploaded_at",)
    readonly_fields = ("uploaded_at", "photo_preview")
    autocomplete_fields = ("service",)
    fieldsets = (
        (None, {"fields": ("service", "photo", "caption")}),
        ("Preview", {"fields": ("photo_preview",)}),
        ("Timestamps", {"fields": ("uploaded_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("service")

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-width:200px;max-height:200px;border:1px solid #eee;border-radius:6px;padding:4px;" />', obj.photo.url)
        return "No photo"
    photo_preview.short_description = "Preview"


@admin.register(ServiceTypePhoto)
class ServiceTypePhotoAdmin(admin.ModelAdmin):
    list_display = ("service_type", "caption", "photo_preview", "uploaded_at")
    list_filter = ("service_type__service", "uploaded_at")
    search_fields = ("service_type__title", "service_type__service__title", "caption")
    ordering = ("-uploaded_at",)
    readonly_fields = ("uploaded_at", "photo_preview")
    autocomplete_fields = ("service_type",)
    fieldsets = (
        (None, {"fields": ("service_type", "photo", "caption")}),
        ("Preview", {"fields": ("photo_preview",)}),
        ("Timestamps", {"fields": ("uploaded_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("service_type", "service_type__service")

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-width:200px;max-height:200px;border:1px solid #eee;border-radius:6px;padding:4px;" />', obj.photo.url)
        return "No photo"
    photo_preview.short_description = "Preview"


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("service", "user", "rating_display", "review_preview", "created_at")
    list_filter = ("rating", "service", "created_at")
    search_fields = ("service__title", "user__email", "review")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    autocomplete_fields = ("service", "user")
    fieldsets = (
        (None, {"fields": ("service", "user", "rating")}),
        ("Review", {"fields": ("review",)}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("service", "user")

    def rating_display(self, obj):
        return format_html("{} {}", obj.rating, "⭐" * int(obj.rating))
    rating_display.short_description = "Rating"

    def review_preview(self, obj):
        if obj.review:
            return (obj.review[:50] + "…") if len(obj.review) > 50 else obj.review
        return "No review"
    review_preview.short_description = "Review"
