from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.html import format_html

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
        'email', 'first_name', 'last_name', 'phone_number',
        'is_provider', 'is_professional', 'is_verified', 'is_active', 'date_joined'
    )
    list_filter = (
        'is_active', 'is_staff', 'is_superuser',
        'is_provider', 'is_professional', 'is_verified', 'date_joined'
    )
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'profile_image')}),
        ('User type', {'fields': ('is_provider', 'is_professional', 'is_verified')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Change password', {'fields': ('new_password1', 'new_password2')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2', 'first_name', 'last_name',
                'is_provider', 'is_professional'
            ),
        }),
    )

    readonly_fields = ('date_joined', 'last_login', 'password')

    def save_model(self, request, obj, form, change):
        # If admin provided a new password, set it properly
        new_pw = form.cleaned_data.get('new_password1')
        if new_pw:
            obj.set_password(new_pw)
        super().save_model(request, obj, form, change)


@admin.register(OneTimeCode)
class OneTimeCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'created_at', 'expires_at', 'is_expired_display', 'is_used_display', 'new_email')
    list_filter = ('purpose', 'created_at', 'expires_at', 'used_at')
    search_fields = ('user__email', 'new_email')
    ordering = ('-created_at',)
    readonly_fields = ('user', 'purpose', 'code_hash', 'new_email', 'created_at', 'expires_at', 'used_at', 'is_expired_display', 'is_used_display')

    fieldsets = (
        (None, {'fields': ('user', 'purpose', 'new_email')}),
        ('Code Details', {'fields': ('code_hash',)}),
        ('Timestamps', {'fields': ('created_at', 'expires_at', 'used_at', 'is_expired_display', 'is_used_display')}),
    )

    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Valid</span>')
    is_expired_display.short_description = 'Status'

    def is_used_display(self, obj):
        if obj.is_used:
            return format_html('<span style="color: orange;">Used</span>')
        return format_html('<span style="color: blue;">Unused</span>')
    is_used_display.short_description = 'Usage'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
