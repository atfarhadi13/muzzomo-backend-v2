from django.db.models import Count, Prefetch, Avg

from rest_framework import generics, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from .models import ServiceCategory, Service, ServiceType, ServicePhoto, Rating, Unit
from .serializers import (
    ServiceCategorySerializer,
    ServiceSerializer,
    ServiceTypeWithServiceSerializer,
    RatingSerializer,
    UnitSerializer,
)

from .permissions import IsOwnerOrReadOnly

class ServiceCategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ServiceCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "created_at", "services_count"]
    ordering = ["title"]

    def get_queryset(self):
        try:
            return (
                ServiceCategory.objects
                .annotate(services_count=Count("services", distinct=True))
                .order_by("title")
            )
        except Exception:
            return ServiceCategory.objects.none()

class ServiceListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ServiceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "types__title"]
    ordering_fields = ["price", "created_at", "avg_rating"]
    ordering = ["title"]

    def _include_types(self) -> bool:
        v = (self.request.query_params.get("include_types") or "").lower()
        return v in {"1", "true", "yes"}

    def get_queryset(self):
        try:
            qs = (
                Service.objects
                .select_related("unit")
                .prefetch_related(
                    "categories",
                    Prefetch("photos", queryset=ServicePhoto.objects.order_by("-uploaded_at")),
                )
                .annotate(avg_rating=Avg("ratings__rating"))
            )

            if self._include_types():
                qs = qs.prefetch_related(
                    Prefetch("types", queryset=ServiceType.objects.prefetch_related("photos").order_by("title"))
                )

            category_id = self.request.query_params.get("category")
            if category_id:
                qs = qs.filter(categories__id=category_id)

            unit_id = self.request.query_params.get("unit")
            if unit_id:
                qs = qs.filter(unit_id=unit_id)

            return qs.distinct()
        except Exception:
            return Service.objects.none()

    def get_serializer_context(self):
        try:
            ctx = super().get_serializer_context()
            ctx["include_types"] = self._include_types()
            return ctx
        except Exception:
            return {}

class ServiceTypeListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ServiceTypeWithServiceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "service__title"]
    ordering_fields = ["title", "price", "created_at"]
    ordering = ["title"]

    def get_queryset(self):
        try:
            qs = ServiceType.objects.select_related("service", "service__unit").order_by("title")
            service_id = self.request.query_params.get("service")
            if service_id:
                qs = qs.filter(service_id=service_id)
            return qs
        except Exception:
            return ServiceType.objects.none()

class ServiceTypeDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ServiceTypeWithServiceSerializer
    queryset = ServiceType.objects.select_related("service", "service__unit")


class RatingListCreateView(generics.ListCreateAPIView):
    queryset = Rating.objects.select_related("service", "user").order_by("-created_at")
    serializer_class = RatingSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["review", "service__title", "user__email"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        try:
            return Rating.objects.select_related("service", "user").order_by("-created_at")
        except Exception:
            return Rating.objects.none()

    def get_serializer_context(self):
        try:
            ctx = super().get_serializer_context()
            return ctx
        except Exception:
            return {}

class RatingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rating.objects.select_related("service", "user")
    serializer_class = RatingSerializer
    permission_classes = [IsOwnerOrReadOnly]


class MyRatingListView(generics.ListAPIView):

    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["review", "service__title"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        try:
            return Rating.objects.select_related("service", "user").filter(user=self.request.user)
        except Exception:
            return Rating.objects.none()

class ServiceRatingListView(generics.ListAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["review", "user__email"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        try:
            service_id = self.kwargs["service_id"]
            return Rating.objects.select_related("service", "user").filter(service_id=service_id)
        except Exception:
            return Rating.objects.none()

class UnitListView(APIView):
    def get(self, request):
        units = Unit.objects.all()
        serializer = UnitSerializer(units, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class UnitDetailView(APIView):
    def get(self, request, pk):
        try:
            unit = Unit.objects.get(pk=pk)
            serializer = UnitSerializer(unit)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Unit.DoesNotExist:
            raise NotFound(detail="Unit not found")