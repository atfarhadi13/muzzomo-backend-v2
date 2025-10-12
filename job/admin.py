import csv

from django.contrib import admin, messages
from django.db.models import Sum, Count
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils import timezone

from .models import (
    Job, JobAttachment, JobServiceType, JobRate,
    JobUnitUpdateRequest, JobOffer, ProfessionalPayout
)


# ------------------ Inlines ------------------

class JobAttachmentInline(admin.TabularInline):
    model = JobAttachment
    extra = 0
    readonly_fields = ('attachment_filename', 'uploaded_at')

    def attachment_filename(self, obj):
        if obj.attachment:
            return obj.attachment.name.split('/')[-1]
        return "-"
    attachment_filename.short_description = "Attachment"


class JobServiceTypeInline(admin.TabularInline):
    model = JobServiceType
    extra = 0
    autocomplete_fields = ['service_type']
    readonly_fields = ('service_type',)


# ------------------ Job ------------------

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'user_email', 'professional_email', 'service',
        'quantity', 'total_price', 'status', 'is_paid', 'created_at',
    )
    list_filter = ('status', 'is_paid', 'service', 'created_at')
    search_fields = (
        'title', 'user__email', 'professional__user__email',
        'address__street_name', 'address__city_name',
    )
    readonly_fields = (
        'submit_date', 'created_at', 'updated_at', 'computed_total_price',
        'paid_amount', 'stripe_session_id', 'total_price'
    )
    autocomplete_fields = ['user', 'professional', 'service', 'address']
    date_hierarchy = 'created_at'
    inlines = [JobAttachmentInline, JobServiceTypeInline]
    list_select_related = ('user', 'professional__user', 'service', 'address')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('service_types')

    def user_email(self, obj):
        email = getattr(obj.user, 'email', None)
        if email:
            return '***@' + email.split('@')[1]
        return None
    user_email.short_description = 'User'

    def professional_email(self, obj):
        email = getattr(getattr(obj.professional, 'user', None), 'email', None)
        if email:
            return '***@' + email.split('@')[1]
        return None
    professional_email.short_description = 'Professional'


# ------------------ JobAttachment ------------------

@admin.register(JobAttachment)
class JobAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'attachment_filename', 'uploaded_at')
    search_fields = ('job__title', 'job__user__email')
    list_filter = ('uploaded_at',)
    autocomplete_fields = ['job']
    date_hierarchy = 'uploaded_at'
    list_select_related = ('job',)

    def attachment_filename(self, obj):
        if obj.attachment:
            return obj.attachment.name.split('/')[-1]
        return "-"
    attachment_filename.short_description = "Attachment"


# ------------------ JobServiceType ------------------

@admin.register(JobServiceType)
class JobServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('job', 'service_type')
    search_fields = ('job__title', 'service_type__title')
    autocomplete_fields = ['job', 'service_type']
    readonly_fields = ('service_type',)
    list_select_related = ('job', 'service_type')


# ------------------ JobRate ------------------

@admin.register(JobRate)
class JobRateAdmin(admin.ModelAdmin):
    list_display = ('job', 'rate', 'rated_at')
    list_filter = ('rate', 'rated_at')
    search_fields = ('job__title', 'job__user__email', 'job__professional__user__email')
    autocomplete_fields = ['job']
    date_hierarchy = 'rated_at'
    list_select_related = ('job',)
    readonly_fields = ('rated_at',)


# ------------------ JobUnitUpdateRequest ------------------

@admin.register(JobUnitUpdateRequest)
class JobUnitUpdateRequestAdmin(admin.ModelAdmin):
    list_display = ('job', 'professional', 'new_unit_qty', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__title', 'professional__user__email')
    autocomplete_fields = ['job', 'professional']
    date_hierarchy = 'created_at'
    list_select_related = ('job', 'professional', 'professional__user')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['accept_selected_requests']

    @admin.action(description='Accept selected unit update requests (only pending)')
    def accept_selected_requests(self, request, queryset):
        processed = 0
        errors = 0
        for req in queryset:
            try:
                with transaction.atomic():
                    req.accept()
                processed += 1
            except ValidationError as e:
                errors += 1
                messages.error(request, f'#{req.id}: {e.messages[0]}')
        if processed:
            messages.success(request, f'Accepted {processed} request(s).')
        if errors and not processed:
            messages.warning(request, 'No requests accepted.')


# ------------------ JobOffer ------------------

@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = ('job', 'professional', 'status', 'distance_km', 'created_at', 'accepted_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__title', 'professional__user__email')
    autocomplete_fields = ['job', 'professional']
    date_hierarchy = 'created_at'
    list_select_related = ('job', 'professional', 'professional__user')
    readonly_fields = ('created_at', 'updated_at', 'accepted_at')
    actions = ['accept_selected_offers']

    @admin.action(description='Accept selected offers (only sent/viewed)')
    def accept_selected_offers(self, request, queryset):
        processed = 0
        errors = 0
        for offer in queryset:
            try:
                with transaction.atomic():
                    offer.accept()
                processed += 1
            except ValidationError as e:
                errors += 1
                messages.error(request, f'Offer #{offer.id}: {e.messages[0]}')
        if processed:
            messages.success(request, f'Accepted {processed} offer(s).')
        if errors and not processed:
            messages.warning(request, 'No offers accepted.')

@admin.register(ProfessionalPayout)
class ProfessionalPayoutAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    list_display = (
        "id",
        "job_link",
        "professional",
        "currency",
        "gross_amount_display",
        "fee_percent_display",
        "fee_amount_display",
        "net_amount_display",
        "status_badge",
        "scheduled_at",
        "paid_at",
        "created_at",
    )
    list_select_related = ("professional", "job",)
    list_filter = (
        "status",
        "currency",
        ("scheduled_at", admin.DateFieldListFilter),
        ("paid_at", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "id",
        "job__id",
        "job__title",
        "professional__id",
        "professional__user__email",
        "professional__user__first_name",
        "professional__user__last_name",
        "dest_institution_name",
        "dest_institution_number",
        "dest_transit_number",
        "dest_account_holder_name",
    )
    readonly_fields = (
        "job",
        "professional",
        "currency",
        "gross_amount",
        "fee_percent_applied",
        "fee_amount",
        "net_amount",
        "status",
        "scheduled_at",
        "paid_at",
        "dest_institution_name",
        "dest_institution_number",
        "dest_transit_number",
        "dest_account_last4",
        "dest_account_holder_name",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Links", {"fields": ("job", "professional")}),
        ("Amounts", {
            "fields": (
                "currency",
                "gross_amount",
                "fee_percent_applied",
                "fee_amount",
                "net_amount",
            )
        }),
        ("Status & Timing", {"fields": ("status", "scheduled_at", "paid_at")}),
        ("Destination Snapshot (optional)", {
            "classes": ("collapse",),
            "fields": (
                "dest_institution_name",
                "dest_institution_number",
                "dest_transit_number",
                "dest_account_last4",
                "dest_account_holder_name",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    actions = [
        "action_mark_scheduled",
        "action_mark_paid",
        "action_mark_failed",
        "action_show_totals",
        "action_export_csv",
    ]

    @admin.display(description="Job", ordering="job_id")
    def job_link(self, obj: ProfessionalPayout):
        return f"#{obj.job_id} — {getattr(obj.job, 'title', '')}"

    @admin.display(description="Gross", ordering="gross_amount")
    def gross_amount_display(self, obj):
        return f"{obj.gross_amount:.2f}"

    @admin.display(description="Fee %", ordering="fee_percent_applied")
    def fee_percent_display(self, obj):
        return f"{obj.fee_percent_applied:.2f}%"

    @admin.display(description="Fee", ordering="fee_amount")
    def fee_amount_display(self, obj):
        return f"{obj.fee_amount:.2f}"

    @admin.display(description="Net", ordering="net_amount")
    def net_amount_display(self, obj):
        return f"{obj.net_amount:.2f}"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj: ProfessionalPayout):
        return obj.get_status_display()

    def action_mark_scheduled(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(status=ProfessionalPayout.STATUS_SCHEDULED, scheduled_at=now)
        self.message_user(request, f"Marked {updated} payout(s) as Scheduled.", level=messages.SUCCESS)
    action_mark_scheduled.short_description = "Mark selected as Scheduled"

    def action_mark_paid(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(status=ProfessionalPayout.STATUS_PAID, paid_at=now)
        self.message_user(request, f"Marked {updated} payout(s) as Paid.", level=messages.SUCCESS)
    action_mark_paid.short_description = "Mark selected as Paid"

    def action_mark_failed(self, request, queryset):
        updated = queryset.update(status=ProfessionalPayout.STATUS_FAILED)
        self.message_user(request, f"Marked {updated} payout(s) as Failed.", level=messages.WARNING)
    action_mark_failed.short_description = "Mark selected as Failed"

    def action_show_totals(self, request, queryset):
        agg = queryset.aggregate(
            count=Count("id"),
            gross=Sum("gross_amount"),
            fee=Sum("fee_amount"),
            net=Sum("net_amount"),
        )
        msg = (
            f"Selected: {agg['count']} payout(s) — "
            f"Gross: {agg['gross'] or 0:.2f} | "
            f"Fees: {agg['fee'] or 0:.2f} | "
            f"Net: {agg['net'] or 0:.2f}"
        )
        self.message_user(request, msg, level=messages.INFO)
    action_show_totals.short_description = "Show totals (count, gross, fees, net) in messages"

    def action_export_csv(self, request, queryset):
        ts = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"payouts_{ts}.csv"
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(resp)
        writer.writerow([
            "id", "job_id", "job_title", "professional_id", "professional_email",
            "currency", "gross_amount", "fee_percent", "fee_amount", "net_amount",
            "status", "scheduled_at", "paid_at", "created_at",
            "dest_institution_name", "dest_institution_number", "dest_transit_number",
            "dest_account_last4", "dest_account_holder_name",
        ])
        for p in queryset.select_related("job", "professional", "professional__user"):
            writer.writerow([
                p.id,
                p.job_id,
                getattr(p.job, "title", ""),
                p.professional_id,
                getattr(getattr(p.professional, "user", None), "email", ""),
                p.currency,
                f"{p.gross_amount:.2f}",
                f"{p.fee_percent_applied:.2f}",
                f"{p.fee_amount:.2f}",
                f"{p.net_amount:.2f}",
                p.get_status_display(),
                p.scheduled_at.isoformat() if p.scheduled_at else "",
                p.paid_at.isoformat() if p.paid_at else "",
                p.created_at.isoformat() if p.created_at else "",
                p.dest_institution_name or "",
                p.dest_institution_number or "",
                p.dest_transit_number or "",
                p.dest_account_last4 or "",
                p.dest_account_holder_name or "",
            ])
        return resp
    action_export_csv.short_description = "Export selected as CSV"