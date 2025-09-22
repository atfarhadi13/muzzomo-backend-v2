from django.db import transaction, IntegrityError

from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework import generics, permissions

from .models import Professional, ProfessionalService, ProfessionalInsurance, ProfessionalTrade, ProfessionalInventory, ProfessionalTask, ProfessionalRating, ProfessionalPayout

from .serializers import  ( ProfessionalSerializer, ProfessionalServiceSerializer, 
                           ProfessionalInsuranceSerializer, ProfessionalTradeSerializer,
                           ProfessionalInventorySerializer, ProfessionalTaskSerializer,
                           ProfessionalRatingSerializer, ProfessionalPayoutSerializer )

from .permissions import IsOwnerOrAdmin

class ProfessionalViewSet(viewsets.ModelViewSet):
    queryset = Professional.objects.select_related("user").all()
    serializer_class = ProfessionalSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

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

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        obj = Professional.objects.filter(user=request.user).first()
        if not obj:
            return Response({"detail": "No professional profile."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(obj).data)
    
class ProfessionalServiceViewSet(viewsets.ModelViewSet):
    queryset = ProfessionalService.objects.select_related("professional__user", "service").all()
    serializer_class = ProfessionalServiceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(professional__user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        pro = Professional.objects.filter(user=self.request.user).first()
        if not pro:
            raise ValidationError({"detail": "Create your professional profile first."})
        try:
            serializer.save(professional=pro)
        except IntegrityError:
            raise ValidationError({"detail": "Service already added for this professional."})
        
class ProfessionalInsuranceViewSet(viewsets.ModelViewSet):
    queryset = ProfessionalInsurance.objects.select_related("professional__user").all()
    serializer_class = ProfessionalInsuranceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(professional__user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        pro = Professional.objects.filter(user=self.request.user).first()
        if not pro:
            raise ValidationError({"detail": "Create your professional profile first."})
        if hasattr(pro, "insurance"):
            raise ValidationError({"detail": "Insurance already exists for this professional."})
        try:
            serializer.save(professional=pro)
        except IntegrityError:
            raise ValidationError({"detail": "Insurance already exists."})

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        obj = ProfessionalInsurance.objects.filter(professional__user=request.user).first()
        if not obj:
            return Response({"detail": "No insurance record."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(obj).data)
    
class ProfessionalTradeViewSet(viewsets.ModelViewSet):
    queryset = ProfessionalTrade.objects.select_related("professional__user").all()
    serializer_class = ProfessionalTradeSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(professional__user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        pro = Professional.objects.filter(user=self.request.user).first()
        if not pro:
            raise ValidationError({"detail": "Create your professional profile first."})
        try:
            serializer.save(professional=pro)
        except IntegrityError:
            raise ValidationError({"detail": "Trade license already exists or violates constraints."})

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        qs = self.get_queryset().filter(professional__user=request.user)
        return Response(self.get_serializer(qs, many=True).data, status=status.HTTP_200_OK)

class ProfessionalInventoryViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalInventorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProfessionalInventory.objects.filter(professional=self.request.user.professional_profile)

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user.professional_profile)

class ProfessionalTaskViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProfessionalTask.objects.filter(professional=self.request.user.professional_profile)

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user.professional_profile)

class ProfessionalRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProfessionalRating.objects.filter(professional=self.request.user.professional_profile)

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user.professional_profile)

class ProfessionalPayoutViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalPayoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProfessionalPayout.objects.filter(professional=self.request.user.professional_profile)

    def perform_create(self, serializer):
        serializer.save(professional=self.request.user.professional_profile)