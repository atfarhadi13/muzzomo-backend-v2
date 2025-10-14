from django.contrib import admin
from django.utils.html import format_html

from .models import Country, Province, City, Address


class ProvinceInline(admin.TabularInline):
    model = Province
    extra = 0
    autocomplete_fields = ["country"]


class CityInline(admin.TabularInline):
    model = City
    extra = 0
    autocomplete_fields = ["province"]


class AddressCountryFilter(admin.SimpleListFilter):
    title = "country"
    parameter_name = "country"

    def lookups(self, request, model_admin):
        return [(str(c.pk), c.name) for c in Country.objects.all().order_by("name")]

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            return queryset.filter(city__province__country_id=val)
        return queryset


class AddressProvinceFilter(admin.SimpleListFilter):
    title = "province"
    parameter_name = "province"

    def lookups(self, request, model_admin):
        qs = Province.objects.select_related("country").order_by("name")
        return [(str(p.pk), f"{p.name} ({p.code})") for p in qs]

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            return queryset.filter(city__province_id=val)
        return queryset


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)
    inlines = [ProvinceInline]


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country")
    list_filter = ("country",)
    search_fields = ("name", "code", "country__name", "country__code")
    autocomplete_fields = ["country"]
    list_select_related = ("country",)
    ordering = ("country__name", "name")
    inlines = [CityInline]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "country_name", "province_code")
    list_filter = ("province__country", "province")
    search_fields = ("name", "province__name", "province__country__name")
    autocomplete_fields = ["province"]
    list_select_related = ("province", "province__country")
    ordering = ("province__country__name", "province__name", "name")

    @admin.display(description="Country")
    def country_name(self, obj):
        return obj.province.country.name

    @admin.display(description="Prov. Code")
    def province_code(self, obj):
        return obj.province.code


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "user_email",
        "street_number",
        "street_name",
        "unit_suite",
        "city",
        "province_code",
        "country_name",
        "postal_code_formatted",
        "latitude",
        "longitude",
        "map_link",
        "date_created",
    )
    list_filter = (AddressCountryFilter, AddressProvinceFilter, "date_created")
    search_fields = (
        "user__email",
        "street_number",
        "street_name",
        "unit_suite",
        "postal_code",
        "city__name",
        "city__province__name",
        "city__province__country__name",
    )
    readonly_fields = ("date_created", "date_updated", "postal_code_formatted", "map_link")
    autocomplete_fields = ["user", "city"]
    date_hierarchy = "date_created"
    list_select_related = ("user", "city", "city__province", "city__province__country")
    ordering = ("-date_created",)
    fieldsets = (
        (
            "Address",
            {
                "fields": (
                    "user",
                    ("street_number", "street_name", "unit_suite"),
                    "city",
                    ("postal_code", "postal_code_formatted"),
                    ("latitude", "longitude"),
                )
            },
        ),
        (
            "Meta",
            {
                "fields": (
                    "map_link",
                    "date_created",
                    "date_updated",
                )
            },
        ),
    )
    actions = ("normalize_postal_codes",)

    @admin.display(description="User")
    def user_email(self, obj):
        return getattr(obj.user, "email", None)

    @admin.display(description="Country")
    def country_name(self, obj):
        return obj.city.province.country.name

    @admin.display(description="Prov. Code")
    def province_code(self, obj):
        return obj.city.province.code

    @admin.display(description="Map")
    def map_link(self, obj):
        q = f"{obj.street_number} {obj.street_name}, {obj.city.name}, {obj.city.province.code}, {obj.postal_code_formatted}"
        return format_html('<a href="https://www.google.com/maps/search/{}" target="_blank">Open</a>', q.replace('"', ""))

    @admin.action(description="Normalize selected postal codes")
    def normalize_postal_codes(self, request, queryset):
        for a in queryset:
            a.full_clean()
            a.save()