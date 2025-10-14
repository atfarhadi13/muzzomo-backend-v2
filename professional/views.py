from decimal import Decimal

from django.db import transaction, IntegrityError

from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework import permissions, filters

from .models import ( 
    Professional, 
    ProfessionalService, 
    ProfessionalInsurance, 
    ProfessionalTrade, 
    ProfessionalInventory, 
    ProfessionalTask, 
    ProfessionalRating, 
    ProfessionalPayout, 
    BankInfo,
    ProfessionalTaskStatus
)

from .serializers import  ( 
    ProfessionalSerializer, 
    ProfessionalServiceSerializer, 
    ProfessionalInsuranceSerializer, 
    ProfessionalTradeSerializer,
    ProfessionalInventorySerializer, 
    ProfessionalTaskSerializer,
    ProfessionalRatingSerializer, 
    ProfessionalPayoutSerializer, 
    BankInfoSerializer 
)

class ProfessionalViewSet(viewsets.ModelViewSet):
    queryset = Professional.objects.select_related("user").all()
    serializer_class = ProfessionalSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["license_number", "user__email"]
    ordering_fields = ["rating_avg", "rating_count", "user__email"]
    ordering = ["user__email"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        if Professional.objects.filter(user=self.request.user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "You already have a professional profile."})
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="rate")
    def rate(self, request, pk=None):
        pro = self.get_object()
        s = ProfessionalRatingCreateUpdateSerializer(data=request.data, context={"request": request, "professional": pro})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(ProfessionalRatingSerializer(obj).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="ratings")
    def ratings(self, request, pk=None):
        pro = self.get_object()
        qs = ProfessionalRating.objects.filter(professional=pro).select_related("user")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ProfessionalRatingSerializer(page, many=True).data)
        return Response(ProfessionalRatingSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="my-rating")
    def my_rating(self, request, pk=None):
        pro = self.get_object()
        obj = ProfessionalRating.objects.filter(professional=pro, user=request.user).first()
        if not obj:
            return Response({"detail": "No rating yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProfessionalRatingSerializer(obj).data)

class ProfessionalServiceViewSet(viewsets.ModelViewSet):
    queryset = ProfessionalService.objects.select_related("professional__user", "service").all()
    serializer_class = ProfessionalServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            if self.request.user.is_staff:
                return self.queryset
            return self.queryset.filter(professional__user=self.request.user)
        except Exception:
            return ProfessionalService.objects.none()

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            pro = Professional.objects.filter(user=self.request.user).first()
            if not pro:
                raise ValidationError({"detail": "Create your professional profile first."})
            serializer.save(professional=pro)
        except IntegrityError:
            raise ValidationError({"detail": "Service already added for this professional."})
        except Exception as e:
            raise ValidationError({"detail": str(e)})

class ProfessionalInsuranceViewSet(viewsets.ModelViewSet):
    queryset = ProfessionalInsurance.objects.select_related("professional__user").all()
    serializer_class = ProfessionalInsuranceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        try:
            if self.request.user.is_staff:
                return self.queryset
            return self.queryset.filter(professional__user=self.request.user)
        except Exception:
            return ProfessionalInsurance.objects.none()

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            pro = Professional.objects.filter(user=self.request.user).first()
            if not pro:
                raise ValidationError({"detail": "Create your professional profile first."})
            if hasattr(pro, "insurance"):
                raise ValidationError({"detail": "Insurance already exists for this professional."})
            serializer.save(professional=pro)
        except IntegrityError:
            raise ValidationError({"detail": "Insurance already exists."})
        except Exception as e:
            raise ValidationError({"detail": str(e)})

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        try:
            obj = ProfessionalInsurance.objects.filter(professional__user=request.user).first()
            if not obj:
                return Response({"detail": "No insurance record."}, status=status.HTTP_404_NOT_FOUND)
            return Response(self.get_serializer(obj).data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProfessionalTradeViewSet(viewsets.ModelViewSet):
    queryset = ProfessionalTrade.objects.select_related("professional__user").all()
    serializer_class = ProfessionalTradeSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        try:
            if self.request.user.is_staff:
                return self.queryset
            return self.queryset.filter(professional__user=self.request.user)
        except Exception:
            return ProfessionalTrade.objects.none()

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            pro = Professional.objects.filter(user=self.request.user).first()
            if not pro:
                raise ValidationError({"detail": "Create your professional profile first."})
            serializer.save(professional=pro)
        except IntegrityError:
            raise ValidationError({"detail": "Trade license already exists or violates constraints."})
        except Exception as e:
            raise ValidationError({"detail": str(e)})

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        try:
            qs = self.get_queryset().filter(professional__user=request.user)
            return Response(self.get_serializer(qs, many=True).data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProfessionalInventoryViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalInventorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["item_name", "description", "unit"]
    ordering_fields = ["item_name", "quantity", "date_added"]
    ordering = ["-date_added"]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            return ProfessionalInventory.objects.none()
        return ProfessionalInventory.objects.filter(professional=prof)

    def perform_create(self, serializer):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Create your professional profile first."})
        serializer.save(professional=prof)

    @action(detail=True, methods=["post"], url_path="adjust")
    def adjust(self, request, pk=None):
        try:
            delta_str = str(request.data.get("delta", "")).strip()
            if not delta_str:
                return Response({"detail": "delta is required."}, status=400)
            delta = Decimal(delta_str)
        except Exception:
            return Response({"detail": "delta must be a number."}, status=400)

        obj = self.get_object()
        with transaction.atomic():
            inv = ProfessionalInventory.objects.select_for_update().get(pk=obj.pk)
            new_qty = inv.quantity + delta
            if new_qty < 0:
                return Response({"detail": "Resulting quantity cannot be negative."}, status=400)
            inv.quantity = new_qty
            inv.save(update_fields=["quantity"])
        return Response(ProfessionalInventorySerializer(inv).data, status=status.HTTP_200_OK)

class ProfessionalTaskViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["worker_name", "worker_email", "description", "status"]
    ordering_fields = ["start_date", "start_time", "price_per_hour", "date_created", "status"]
    ordering = ["-date_created"]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            return ProfessionalTask.objects.none()
        return ProfessionalTask.objects.filter(professional=prof)

    def perform_create(self, serializer):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Create your professional profile first."})
        serializer.save(professional=prof)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        obj = self.get_object()
        with transaction.atomic():
            t = ProfessionalTask.objects.select_for_update().get(pk=obj.pk)
            if t.end_time is None:
                now = timezone.localtime()
                t.end_time = now.time()
            t.status = ProfessionalTaskStatus.COMPLETED
            t.save(update_fields=["end_time", "status"])
        return Response(ProfessionalTaskSerializer(t).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        new_status = str(request.data.get("status", "")).strip().lower()
        if new_status not in dict(ProfessionalTaskStatus.choices):
            return Response({"detail": "Invalid status."}, status=400)
        obj = self.get_object()
        with transaction.atomic():
            t = ProfessionalTask.objects.select_for_update().get(pk=obj.pk)
            t.status = new_status
            t.save(update_fields=["status"])
        return Response(ProfessionalTaskSerializer(t).data, status=200)

class ProfessionalRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalRatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = ProfessionalRating.objects.select_related("professional__user", "user")
        prof_id = self.request.query_params.get("professional")
        if prof_id:
            return qs.filter(professional_id=prof_id)
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

class ProfessionalPayoutViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalPayoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        try:
            return ProfessionalPayout.objects.filter(professional=self.request.user.professional_profile)
        except Exception:
            return ProfessionalPayout.objects.none()

    def perform_create(self, serializer):
        try:
            serializer.save(professional=self.request.user.professional_profile)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(e)})
        
class BankInfoViewSet(viewsets.ModelViewSet):
    serializer_class = BankInfoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            return BankInfo.objects.none()
        return BankInfo.objects.filter(professional=prof)

    def perform_create(self, serializer):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "User is not a professional."})

        data = serializer.validated_data
        obj, _created = BankInfo.objects.update_or_create(
            professional=prof,
            defaults=data,
        )
        serializer.instance = obj

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        prof = getattr(request.user, "professional_profile", None)
        if not prof:
            return Response({"detail": "User is not a professional."}, status=status.HTTP_400_BAD_REQUEST)
        obj = BankInfo.objects.filter(professional=prof).first()
        if not obj:
            return Response({"detail": "No bank info found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(obj).data)