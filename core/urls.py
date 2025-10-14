from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include('user.urls')),
    path('service/', include('service.urls')),
    path('address/', include('address.urls')),
    path('professional/', include('professional.urls')),
    path('job/', include('job.urls')),
    path("api/subscriptions/", include("subscription.urls", namespace="subscriptions")),
    path("api/project_management", include("project_management.urls")),
    path("api/inventory", include("inventory.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
