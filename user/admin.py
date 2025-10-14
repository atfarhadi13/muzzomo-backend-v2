from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm

from .models import CustomUser, OneTimeCode


class CustomUserChangeForm(UserChangeForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput,
        required=False,
        help_text="Leave blank to keep the current password."
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput,
        required=False
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


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    model = CustomUser

    list_display = (
        "email", "first_name", "last_name", "phone_number",
        "is_provider", "is_professional", "is_verified", "is_active",
        "failed_login_attempts", "locked_until", "date_joined",
    )
    list_filter = (
        "is_active", "is_staff", "is_superuser",
        "is_provider", "is_professional", "is_verified",
    )
    search_fields = ("email", "first_name", "last_name", "phone_number", "stripe_customer_id")
    ordering = ("email",)

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
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "password1", "password2",
                "first_name", "last_name", "phone_number",
                "is_provider", "is_professional", "is_verified", "is_active",
            ),
        }),
    )

    readonly_fields = ("date_joined", "last_login", "email_verified_at")

    def save_model(self, request, obj, form, change):
        new_pw = form.cleaned_data.get("new_password1")
        if new_pw:
            obj.set_password(new_pw)
        super().save_model(request, obj, form, change)


@admin.register(OneTimeCode)
class OneTimeCodeAdmin(admin.ModelAdmin):
    list_display = (
        "user", "purpose", "new_email", "created_at", "expires_at",
        "used_at", "verify_attempts", "max_attempts",
    )
    list_filter = ("purpose", "used_at", "expires_at", "created_at")
    search_fields = ("user__email", "new_email")
    ordering = ("-created_at",)
    readonly_fields = ("user", "purpose", "new_email", "code_hash", "created_at", "expires_at", "used_at", "verify_attempts", "max_attempts")

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
