from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.http import HttpResponseRedirect

from .models import AppSettings


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "site_name",
        "maintenance_mode",
        "locale",
        "version",
        "updated_at",
        "logo_thumb",
        "favicon_thumb",
    )
    list_filter = ("maintenance_mode", "locale", "updated_at")
    search_fields = (
        "site_name",
        "support_email",
        "support_phone",
        "website_url",
        "ios_store_url",
        "android_store_url",
        "version",
    )
    readonly_fields = (
        "logo_preview",
        "favicon_preview",
        "version",
        "created_at",
        "updated_at",
        "theme_preview",
    )
    fieldsets = (
        (_("Branding"), {
            "fields": (
                "site_name",
                ("primary_color", "secondary_color"),
                "font_family",
                ("logo", "logo_preview"),
                ("favicon", "favicon_preview"),
                "theme_preview",
            )
        }),
        (_("Content"), {
            "fields": ("privacy_policy", "terms_and_conditions")
        }),
        (_("Support & Links"), {
            "fields": (
                "support_email",
                "support_phone",
                "website_url",
                ("ios_store_url", "android_store_url"),
            )
        }),
        (_("Behavior"), {
            "fields": ("maintenance_mode", "locale", "extra")
        }),
        (_("Versioning & Timestamps"), {
            "fields": ("version", "created_at", "updated_at")
        }),
    )
    actions = ("toggle_maintenance", "bump_versions", "clear_logo", "clear_favicon")

    def has_add_permission(self, request):
        if AppSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(None)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "open/",
                self.admin_site.admin_view(self.open_singleton),
                name="appsettings_open_singleton",
            )
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        qs = AppSettings.objects.all()
        if qs.count() == 1:
            obj = qs.first()
            return HttpResponseRedirect(f"./{obj.pk}/change/")
        return super().changelist_view(request, extra_context)

    def open_singleton(self, request):
        obj, _ = AppSettings.objects.get_or_create()
        return HttpResponseRedirect(f"../{obj.pk}/change/")

    @admin.display(description=_("Logo"))
    def logo_thumb(self, obj):
        if not obj.logo:
            return "-"
        return format_html('<img src="{}" style="height:24px;width:auto;border-radius:4px;" />', obj.logo.url)

    @admin.display(description=_("Favicon"))
    def favicon_thumb(self, obj):
        if not obj.favicon:
            return "-"
        return format_html('<img src="{}" style="height:16px;width:16px;border-radius:4px;" />', obj.favicon.url)

    @admin.display(description=_("Logo preview"))
    def logo_preview(self, obj):
        if not obj.logo:
            return "-"
        return format_html('<img src="{}" style="max-height:80px;width:auto;border:1px solid #e5e7eb;border-radius:8px;padding:4px;background:#fff;" />', obj.logo.url)

    @admin.display(description=_("Favicon preview"))
    def favicon_preview(self, obj):
        if not obj.favicon:
            return "-"
        return format_html('<img src="{}" style="height:32px;width:32px;border:1px solid #e5e7eb;border-radius:6px;padding:2px;background:#fff;" />', obj.favicon.url)

    @admin.display(description=_("Theme preview"))
    def theme_preview(self, obj):
        primary = obj.primary_color or "#0ea5e9"
        secondary = obj.secondary_color or "#1f2937"
        font = obj.font_family or "system-ui"
        html = f"""
        <div style="display:flex;gap:12px;align-items:center;font-family:{font};">
          <div style="width:28px;height:28px;background:{primary};border-radius:6px;border:1px solid #e5e7eb;"></div>
          <div style="width:28px;height:28px;background:{secondary};border-radius:6px;border:1px solid #e5e7eb;"></div>
          <span style="opacity:.75;">{primary} / {secondary}</span>
        </div>
        """
        return mark_safe(html)

    @admin.action(description=_("Toggle maintenance mode"))
    def toggle_maintenance(self, request, queryset):
        updated = 0
        for obj in queryset:
            obj.maintenance_mode = not obj.maintenance_mode
            obj.save(update_fields=["maintenance_mode", "updated_at"])
            updated += 1
        messages.success(request, _(f"Toggled maintenance mode on {updated} record(s)."))

    @admin.action(description=_("Bump version"))
    def bump_versions(self, request, queryset):
        for obj in queryset:
            obj.bump_version()
        messages.success(request, _("Version bumped."))

    @admin.action(description=_("Clear logo"))
    def clear_logo(self, request, queryset):
        cleared = 0
        for obj in queryset:
            if obj.logo:
                storage, name = obj.logo.storage, obj.logo.name
                obj.logo.delete(save=False)
                obj.save(update_fields=["logo", "updated_at"])
                try:
                    if storage and name:
                        storage.delete(name)
                except Exception:
                    pass
                cleared += 1
        messages.success(request, _(f"Cleared logo for {cleared} record(s)."))

    @admin.action(description=_("Clear favicon"))
    def clear_favicon(self, request, queryset):
        cleared = 0
        for obj in queryset:
            if obj.favicon:
                storage, name = obj.favicon.storage, obj.favicon.name
                obj.favicon.delete(save=False)
                obj.save(update_fields=["favicon", "updated_at"])
                try:
                    if storage and name:
                        storage.delete(name)
                except Exception:
                    pass
                cleared += 1
        messages.success(request, _(f"Cleared favicon for {cleared} record(s)."))