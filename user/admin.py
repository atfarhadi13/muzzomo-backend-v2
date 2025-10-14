from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils import timezone
from django.utils.html import format_html

from .models import CustomUser, OneTimeCode


class CustomUserChangeForm(UserChangeForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput,
        required=False,
        help_text="Leave blank to keep the current password.",
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")
        if p1 or p2:
            if not p1 or not p2:
                raise forms.ValidationError("Please enter the new password twice.")
            if p1 != p2:
                raise forms.ValidationError("The two password fields didn’t match.")
        return cleaned


class LockedStatusFilter(admin.SimpleListFilter):
    title = "locked status"
    parameter_name = "locked"

    def lookups(self, request, model_admin):
        return (("yes", "Locked"), ("no", "Not locked"))

    def queryset(self, request, queryset):
        val = self.value()
        now = timezone.now()
        if val == "yes":
            return queryset.filter(locked_until__gt=now)
        if val == "no":
            return queryset.filter((~admin.models.Q(locked_until__gt=now)) | admin.models.Q(locked_until__isnull=True))
        return queryset


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    model = CustomUser

    list_display = (
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "avatar",
        "is_provider",
        "is_professional",
        "is_verified",
        "is_active",
        "is_locked_display",
        "failed_login_attempts",
        "locked_until",
        "date_joined",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "is_provider",
        "is_professional",
        "is_verified",
        LockedStatusFilter,
        "date_joined",
    )
    search_fields = ("email", "first_name", "last_name", "phone_number", "stripe_customer_id")
    ordering = ("email",)
    date_hierarchy = "date_joined"
    actions = ["unlock_accounts", "mark_verified", "mark_unverified", "reset_login_failures"]

    fieldsets = (
        (None, {"fields": ("email",)}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number", "profile_image")}),
        ("Verification", {"fields": ("is_verified", "email_verified_at")}),
        ("User type", {"fields": ("is_provider", "is_professional")}),
        ("Security", {"fields": ("failed_login_attempts", "locked_until")}),
        ("Stripe", {"fields": ("stripe_customer_id",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Change password", {"fields": ("new_password1", "new_password2")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "phone_number",
                    "is_provider",
                    "is_professional",
                    "is_verified",
                    "is_active",
                ),
            },
        ),
    )

    readonly_fields = ("date_joined", "last_login", "email_verified_at")

    def save_model(self, request, obj, form, change):
        new_pw = form.cleaned_data.get("new_password1")
        if new_pw:
            obj.set_password(new_pw)
        super().save_model(request, obj, form, change)

    @admin.display(description="Locked", boolean=True)
    def is_locked_display(self, obj):
        return obj.is_locked

    @admin.display(description="Avatar")
    def avatar(self, obj):
        if obj.profile_image:
            return format_html('<img src="{}" style="height:32px;width:32px;object-fit:cover;border-radius:50%;" />', obj.profile_image.url)
        return "-"

    @admin.action(description="Unlock selected accounts")
    def unlock_accounts(self, request, queryset):
        queryset.update(locked_until=None, failed_login_attempts=0)

    @admin.action(description="Mark selected as verified")
    def mark_verified(self, request, queryset):
        now = timezone.now()
        for u in queryset:
            if not u.is_verified:
                u.is_verified = True
                if not u.email_verified_at:
                    u.email_verified_at = now
                u.save(update_fields=["is_verified", "email_verified_at"])

    @admin.action(description="Mark selected as unverified")
    def mark_unverified(self, request, queryset):
        queryset.update(is_verified=False)

    @admin.action(description="Reset login failure counters")
    def reset_login_failures(self, request, queryset):
        queryset.update(failed_login_attempts=0, locked_until=None)


class ActiveCodeFilter(admin.SimpleListFilter):
    title = "active"
    parameter_name = "active"

    def lookups(self, request, model_admin):
        return (("yes", "Active (unused & not expired)"), ("no", "Inactive/expired"))

    def queryset(self, request, queryset):
        now = timezone.now()
        val = self.value()
        if val == "yes":
            return queryset.filter(used_at__isnull=True, expires_at__gt=now)
        if val == "no":
            return queryset.exclude(used_at__isnull=True, expires_at__gt=now)
        return queryset


@admin.register(OneTimeCode)
class OneTimeCodeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "purpose",
        "new_email",
        "created_at",
        "expires_at",
        "used_at",
        "is_active_display",
        "verify_attempts",
        "max_attempts",
    )
    list_filter = ("purpose", ActiveCodeFilter, "used_at", "expires_at", "created_at")
    search_fields = ("user__email", "new_email")
    ordering = ("-created_at",)
    readonly_fields = ("user", "purpose", "new_email", "code_hash", "created_at", "expires_at", "used_at", "verify_attempts", "max_attempts")
    actions = ["expire_now", "reset_attempts"]
    fieldsets = (
        (None, {"fields": ("user", "purpose", "new_email")}),
        ("Code info", {"fields": ("code_hash",)}),
        ("Attempts", {"fields": ("verify_attempts", "max_attempts")}),
        ("Timestamps", {"fields": ("created_at", "expires_at", "used_at")}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Active", boolean=True)
    def is_active_display(self, obj):
        now = timezone.now()
        return obj.used_at is None and obj.expires_at > now

    @admin.action(description="Expire selected codes now")
    def expire_now(self, request, queryset):
        now = timezone.now()
        for code in queryset:
            if code.used_at is None:
                code.used_at = now
                code.save(update_fields=["used_at"])

    @admin.action(description="Reset verify attempts to 0")
    def reset_attempts(self, request, queryset):
        queryset.update(verify_attempts=0)
