from django.urls import path

from .views import  ( 
    AddressCreateView, 
    AddressDetailView, 
    AddressListForUserView,
    CityDetailView,
    CityListView,
    CountryDetailView,
    CountryListView,
    ProvinceDetailView,
    ProvinceListView,
    
)

urlpatterns = [
    path("addresses/", AddressCreateView.as_view(), name="address-create"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address-detail"),

    path("addresses-list/", AddressListForUserView.as_view(), name="address-list-for-user"),

    # Country URLs
    path('countries/', CountryListView.as_view(), name='country-list'),
    path('countries/<int:pk>/', CountryDetailView.as_view(), name='country-detail'),

    # Province URLs
    path('countries/<int:country_id>/provinces/', ProvinceListView.as_view(), name='province-list'),
    path('countries/<int:country_id>/provinces/<int:province_id>/', ProvinceDetailView.as_view(), name='province-detail'),

    # City URLs
    path('countries/<int:country_id>/provinces/<int:province_id>/cities/', CityListView.as_view(), name='city-list'),
    path('countries/<int:country_id>/provinces/<int:province_id>/cities/<int:city_id>/', CityDetailView.as_view(), name='city-detail'),
]