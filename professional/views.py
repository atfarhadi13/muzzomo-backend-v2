from django.db import transaction, IntegrityError

from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework import generics, permissions

from .models import ( 
    Professional, 
    ProfessionalService, 
    ProfessionalInsurance, 
    ProfessionalTrade, 
    ProfessionalInventory, 
    ProfessionalTask, 
    ProfessionalRating, 
    ProfessionalPayout, 
    BankInfo 
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
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        try:
            if self.request.user.is_staff:
                return self.queryset
            return self.queryset.filter(user=self.request.user)
        except Exception:
            return Professional.objects.none()

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            if Professional.objects.filter(user=self.request.user).exists():
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"detail": "You already have a professional profile."})
            serializer.save(user=self.request.user)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(e)})

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        try:
            obj = Professional.objects.filter(user=request.user).first()
            if not obj:
                return Response({"detail": "No professional profile."}, status=status.HTTP_404_NOT_FOUND)
            return Response(self.get_serializer(obj).data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

    def get_queryset(self):
        try:
            return ProfessionalInventory.objects.filter(professional=self.request.user.professional_profile)
        except Exception:
            return ProfessionalInventory.objects.none()

    def perform_create(self, serializer):
        try:
            serializer.save(professional=self.request.user.professional_profile)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(e)})

class ProfessionalTaskViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        try:
            return ProfessionalTask.objects.filter(professional=self.request.user.professional_profile)
        except Exception:
            return ProfessionalTask.objects.none()

    def perform_create(self, serializer):
        try:
            serializer.save(professional=self.request.user.professional_profile)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(e)})

class ProfessionalRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ProfessionalRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        try:
            return ProfessionalRating.objects.filter(professional=self.request.user.professional_profile)
        except Exception:
            return ProfessionalRating.objects.none()

    def perform_create(self, serializer):
        try:
            serializer.save(professional=self.request.user.professional_profile)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(e)})

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