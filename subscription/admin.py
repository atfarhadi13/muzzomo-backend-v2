from django.contrib import admin
from django.utils.html import format_html

from .models import SubscriptionPlan, UserSubscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "stripe_plan_id", "price", "short_description")
    list_filter = ("price",)
    search_fields = ("name", "stripe_plan_id")
    ordering = ("price",)
    readonly_fields = ()

    @admin.display(description="Description")
    def short_description(self, obj):
        if not obj.description:
            return "-"
        text = str(obj.description)
        return (text[:80] + "…") if len(text) > 80 else text


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user_email",
        "plan",
        "active_badge",
        "stripe_subscription_id",
        "start_date",
        "end_date",
        "trial_end",
    )
    list_filter = ("active", "plan", "start_date", "end_date", "trial_end")
    search_fields = ("user__email", "stripe_subscription_id")
    ordering = ("-start_date",)
    list_select_related = ("user", "plan")
    autocomplete_fields = ("user", "plan")
    readonly_fields = ()

    @admin.display(description="User", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Active")
    def active_badge(self, obj):
        color = "#16a34a" if obj.active else "#ef4444"
        label = "Active" if obj.active else "Inactive"
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;color:white;background:{};">{}</span>',
            color,
            label,
        )
