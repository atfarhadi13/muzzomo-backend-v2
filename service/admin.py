from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg
from .models import ServiceCategory, Unit, Service, ServiceType, ServicePhoto, ServiceTypePhoto, Rating


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'description_preview', 'services_count', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('title',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {'fields': ('title', 'photo', 'description')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    
    def description_preview(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_preview.short_description = 'Description'
    
    def services_count(self, obj):
        return obj.services.count()
    services_count.short_description = 'Services Count'


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'services_count', 'created_at')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {'fields': ('name', 'code')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    
    def services_count(self, obj):
        return obj.services.count()
    services_count.short_description = 'Services Count'


class ServicePhotoInline(admin.TabularInline):
    model = ServicePhoto
    extra = 0
    readonly_fields = ('uploaded_at',)
    fields = ('photo', 'caption', 'uploaded_at')


class ServiceTypeInline(admin.TabularInline):
    model = ServiceType
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('title', 'description', 'price', 'created_at')
    show_change_link = True


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 0
    readonly_fields = ('user', 'rating', 'review', 'created_at')
    fields = ('user', 'rating', 'review', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'unit', 'is_trade_required', 'categories_display', 'average_rating_display', 'types_count', 'created_at')
    list_filter = ('is_trade_required', 'categories', 'unit', 'created_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('categories',)
    ordering = ('title',)
    readonly_fields = ('created_at', 'average_rating_display')
    inlines = [ServiceTypeInline, ServicePhotoInline, RatingInline]
    
    fieldsets = (
        (None, {'fields': ('title', 'description')}),
        ('Pricing & Requirements', {'fields': ('price', 'unit', 'is_trade_required')}),
        ('Categories', {'fields': ('categories',)}),
        ('Statistics', {'fields': ('average_rating_display',)}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    
    def categories_display(self, obj):
        return ', '.join([cat.title for cat in obj.categories.all()[:3]])
    categories_display.short_description = 'Categories'
    
    def average_rating_display(self, obj):
        avg_rating = obj.average_rating
        if avg_rating:
            stars = '⭐' * int(avg_rating)
            return format_html(f'{avg_rating} {stars}')
        return 'No ratings'
    average_rating_display.short_description = 'Average Rating'
    
    def types_count(self, obj):
        return obj.types.count()
    types_count.short_description = 'Types Count'


class ServiceTypePhotoInline(admin.TabularInline):
    model = ServiceTypePhoto
    extra = 0
    readonly_fields = ('uploaded_at',)
    fields = ('photo', 'caption', 'uploaded_at')


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('title', 'service', 'price', 'description_preview', 'photos_count', 'created_at')
    list_filter = ('service', 'created_at')
    search_fields = ('title', 'description', 'service__title')
    ordering = ('service', 'title')
    readonly_fields = ('created_at',)
    inlines = [ServiceTypePhotoInline]
    
    fieldsets = (
        (None, {'fields': ('service', 'title', 'description')}),
        ('Pricing', {'fields': ('price',)}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    
    def description_preview(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_preview.short_description = 'Description'
    
    def photos_count(self, obj):
        return obj.photos.count()
    photos_count.short_description = 'Photos Count'


@admin.register(ServicePhoto)
class ServicePhotoAdmin(admin.ModelAdmin):
    list_display = ('service', 'caption', 'photo_preview', 'uploaded_at')
    list_filter = ('service', 'uploaded_at')
    search_fields = ('service__title', 'caption')
    ordering = ('-uploaded_at',)
    readonly_fields = ('uploaded_at', 'photo_preview')
    
    fieldsets = (
        (None, {'fields': ('service', 'photo', 'caption')}),
        ('Preview', {'fields': ('photo_preview',)}),
        ('Timestamps', {'fields': ('uploaded_at',)}),
    )
    
    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-width: 200px; max-height: 200px;" />', obj.photo.url)
        return 'No photo'
    photo_preview.short_description = 'Preview'


@admin.register(ServiceTypePhoto)
class ServiceTypePhotoAdmin(admin.ModelAdmin):
    list_display = ('service_type', 'caption', 'photo_preview', 'uploaded_at')
    list_filter = ('service_type__service', 'uploaded_at')
    search_fields = ('service_type__title', 'service_type__service__title', 'caption')
    ordering = ('-uploaded_at',)
    readonly_fields = ('uploaded_at', 'photo_preview')
    
    fieldsets = (
        (None, {'fields': ('service_type', 'photo', 'caption')}),
        ('Preview', {'fields': ('photo_preview',)}),
        ('Timestamps', {'fields': ('uploaded_at',)}),
    )
    
    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-width: 200px; max-height: 200px;" />', obj.photo.url)
        return 'No photo'
    photo_preview.short_description = 'Preview'


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('service', 'user', 'rating_display', 'review_preview', 'created_at')
    list_filter = ('rating', 'service', 'created_at')
    search_fields = ('service__title', 'user__email', 'review')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {'fields': ('service', 'user', 'rating')}),
        ('Review', {'fields': ('review',)}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    
    def rating_display(self, obj):
        stars = '⭐' * obj.rating
        return format_html(f'{obj.rating} {stars}')
    rating_display.short_description = 'Rating'
    
    def review_preview(self, obj):
        if obj.review:
            return obj.review[:50] + '...' if len(obj.review) > 50 else obj.review
        return 'No review'
    review_preview.short_description = 'Review'
