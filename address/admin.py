# address/admin.py
from django.contrib import admin

from .models import Country, Province, City, Address


# ----------------- Inlines -----------------

class ProvinceInline(admin.TabularInline):
    model = Province
    extra = 0
    autocomplete_fields = ['country']


class CityInline(admin.TabularInline):
    model = City
    extra = 0
    autocomplete_fields = ['province']


# ----------------- Filters -----------------

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


# ----------------- Country -----------------

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    inlines = [ProvinceInline]


# ----------------- Province -----------------

@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country")
    list_filter = ("country",)
    search_fields = ("name", "code", "country__name", "country__code")
    autocomplete_fields = ["country"]
    inlines = [CityInline]
    list_select_related = ("country",)


# ----------------- City -----------------

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "country_name", "province_code")
    list_filter = ("province__country", "province")
    search_fields = ("name", "province__name", "province__country__name")
    autocomplete_fields = ["province"]
    list_select_related = ("province", "province__country")

    @admin.display(description="Country")
    def country_name(self, obj):
        return obj.province.country.name

    @admin.display(description="Prov. Code")
    def province_code(self, obj):
        return obj.province.code


# ----------------- Address -----------------

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "user_email", "street_number", "street_name", "unit_suite",
        "city", "province_code", "country_name",
        "postal_code_formatted", "latitude", "longitude",
        "date_created",
    )
    list_filter = (AddressCountryFilter, AddressProvinceFilter, "date_created")
    search_fields = (
        "user__email", "street_number", "street_name", "unit_suite",
        "postal_code", "city__name", "city__province__name",
        "city__province__country__name",
    )
    readonly_fields = ("date_created", "date_updated")
    autocomplete_fields = ["user", "city"]
    date_hierarchy = "date_created"
    list_select_related = ("user", "city", "city__province", "city__province__country")
    ordering = ("-date_created",)

    @admin.display(description="User")
    def user_email(self, obj):
        return getattr(obj.user, "email", None)

    @admin.display(description="Country")
    def country_name(self, obj):
        return obj.city.province.country.name

    @admin.display(description="Prov. Code")
    def province_code(self, obj):
        return obj.city.province.code
