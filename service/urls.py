from django.urls import path

from .views import ( 
    ServiceCategoryListView, 
    ServiceListView, 
    ServiceTypeListView, 
    ServiceTypeDetailView,
    RatingListCreateView, 
    RatingDetailView,
    MyRatingListView,
    ServiceRatingListView
)

urlpatterns = [
    path("categories/", ServiceCategoryListView.as_view(), name="service-category-list"),
    path("services/", ServiceListView.as_view(), name="service-list"),
    
    path("service-types/", ServiceTypeListView.as_view(), name="service-type-list"),
    path("service-types/<int:pk>/", ServiceTypeDetailView.as_view(), name="service-type-detail"),
    
    path("ratings/", RatingListCreateView.as_view(), name="rating-list-create"),
    path("ratings/<int:pk>/", RatingDetailView.as_view(), name="rating-detail"),
    path("ratings/mine/", MyRatingListView.as_view(), name="rating-mine"),
    path("services/<int:service_id>/ratings/", ServiceRatingListView.as_view(), name="service-rating-list"),
]
