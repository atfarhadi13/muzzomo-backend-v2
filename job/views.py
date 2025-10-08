import re

import stripe

from datetime import datetime, date, time
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from job.serializers import ( 
    JobCreateSerializer, JobRateSerializer, 
    JobListSerializer, JobDetailSerializer,
    JobUnitUpdateRequestCreateSerializer, 
    JobOfferSerializer, JobServiceTypeItemSerializer,
    JobAttachmentSerializer, JobAddressSerializer,
    JobUnitUpdateRequestListSerializer                             
)

from job.models import ( 
    Job, JobServiceType, JobAttachment, 
    JobOffer, JobStatus, JobRate,
    JobUnitUpdateRequest, JobUnitUpdateRequestStatus,
    JobOfferStatus
)

from professional.models import Professional, ProfessionalService
from address.models import Address, Country, Province, City
from service.models import ServiceType

stripe.api_key = settings.STRIPE_SECRET_KEY

class JobCreateView(generics.CreateAPIView):
    serializer_class = JobCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _coerce_date(val):
        if not val:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, str):
            return date.fromisoformat(val)
        raise ValueError("start_date must be a date or ISO date string")

    @staticmethod
    def _coerce_time(val):
        if not val:
            return None
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            return time.fromisoformat(val)
        raise ValueError("start_time must be a time or ISO time string")

    def _make_start_at(self, start_date, start_time):
        d = self._coerce_date(start_date)
        t = self._coerce_time(start_time)
        if not d or not t:
            return None
        dt = datetime.combine(d, t)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    @staticmethod
    def _extract_address_from_form(data):
        keys = [
            "address[street_number]",
            "address[street_name]",
            "address[unit_suite]",
            "address[city_name]",
            "address[province_name]",
            "address[country_name]",
            "address[postal_code]",
        ]
        if not any(k in data for k in keys):
            return None
        return {
            "street_number": data.get("address[street_number]"),
            "street_name": data.get("address[street_name]"),
            "unit_suite": data.get("address[unit_suite]"),
            "city_name": data.get("address[city_name]"),
            "province_name": data.get("address[province_name]"),
            "country_name": data.get("address[country_name]"),
            "postal_code": data.get("address[postal_code]"),
        }

    @staticmethod
    def _extract_service_types_from_form(data):
        pattern = re.compile(r"^job_service_types\[(\d+)\]\[service_type_id\]$")
        items = []
        for k, v in data.items():
            m = pattern.match(k)
            if m:
                items.append((int(m.group(1)), v))
        if not items:
            return None
        items.sort(key=lambda x: x[0])
        return [{"service_type_id": int(val)} for _, val in items if str(val).isdigit()]

    @staticmethod
    def _resolve_address(user, data: dict) -> Address:
        required = ["country_name", "province_name", "city_name", "street_number", "street_name", "postal_code"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise ValueError(f"Address fields missing/empty: {', '.join(missing)}")

        country = Country.objects.filter(name__iexact=data["country_name"]).first()
        if not country:
            raise ValueError("Country not found. Seed countries first.")
        province = Province.objects.filter(name__iexact=data["province_name"], country=country).first()
        if not province:
            raise ValueError("Province not found for the given country.")
        city, _ = City.objects.get_or_create(name=data["city_name"], province=province)
        addr = Address(
            user=user,
            street_number=data["street_number"],
            street_name=data["street_name"],
            unit_suite=data.get("unit_suite") or None,
            city=city,
            postal_code=data["postal_code"],
        )
        addr.full_clean()
        addr.save()
        return addr

    @staticmethod
    def _create_job_offers(job):
        city = job.address.city
        service = job.service
        start_at = job.start_at

        print(f'city : {city}')
        print(f'service : {service}')
        print(f'start_at : {start_at}')

        professionals_in_city = Professional.objects.filter(
            user__addresses__city=city,
            verification_status='approved',
            is_verified=True
        ).distinct()
        pros_with_service = ProfessionalService.objects.filter(
            service=service,
            professional__in=professionals_in_city
        ).values_list('professional_id', flat=True)
        qs = Professional.objects.filter(id__in=pros_with_service)
        if start_at:
            qs = qs.exclude(
                assigned_jobs__status__in=[JobStatus.IN_PROGRESS, JobStatus.PENDING],
                assigned_jobs__start_at__lte=start_at,
                assigned_jobs__completed_date__gte=start_at
            )
        available_pros = qs.distinct()
        JobOffer.objects.bulk_create([JobOffer(job=job, professional=pro) for pro in available_pros])
        return available_pros.count()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        user = request.user

        try:
            address_payload = data.get("address")
            if isinstance(address_payload, dict):
                addr_payload = address_payload
            else:
                addr_payload = self._extract_address_from_form(data) or {}

            st_inputs = data.get("job_service_types")
            if not isinstance(st_inputs, list):
                st_inputs = self._extract_service_types_from_form(data) or []

            start_date = data.get("start_date")
            start_time = data.get("start_time")

            address = self._resolve_address(user, addr_payload)
            data["address"] = address.id

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            job = serializer.save(
                user=user,
                quantity=Decimal("1.00"),
                start_at=self._make_start_at(start_date, start_time),
            )

            if st_inputs:
                st_ids = [int(x["service_type_id"]) for x in st_inputs]
                JobServiceType.objects.bulk_create(
                    [JobServiceType(job=job, service_type_id=st_id) for st_id in st_ids]
                )

            file_list = request.FILES.getlist("job_attachments") if hasattr(request.FILES, "getlist") else []
            for f in file_list:
                JobAttachment.objects.create(job=job, attachment=f)

            offer_count = self._create_job_offers(job)
            return Response(
                {"job_id": job.id, "message": f"Job created successfully. Offered to {offer_count} professionals."},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            transaction.set_rollback(True)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class JobUpdateView(generics.UpdateAPIView):
    serializer_class = JobCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user)

    @staticmethod
    def _first(val):
        if isinstance(val, (list, tuple)):
            return val[0] if val else None
        return val

    @staticmethod
    def _coerce_date(val):
        v = JobUpdateView._first(val)
        if not v:
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return date.fromisoformat(v)
        raise ValueError("start_date must be a date or ISO date string")

    @staticmethod
    def _coerce_time(val):
        v = JobUpdateView._first(val)
        if not v:
            return None
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            return time.fromisoformat(v)
        raise ValueError("start_time must be a time or ISO time string")

    def _make_start_at(self, start_date, start_time):
        d = self._coerce_date(start_date)
        t = self._coerce_time(start_time)
        if d is None and t is None:
            return None
        if not d or not t:
            raise ValueError("Both start_date and start_time are required to update start_at.")
        dt = datetime.combine(d, t)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    @staticmethod
    def _extract_address_from_form(data):
        keys = [
            "address[street_number]",
            "address[street_name]",
            "address[unit_suite]",
            "address[city_name]",
            "address[province_name]",
            "address[country_name]",
            "address[postal_code]",
        ]
        if not any(k in data for k in keys):
            return None
        return {
            "street_number": JobUpdateView._first(data.get("address[street_number]")),
            "street_name": JobUpdateView._first(data.get("address[street_name]")),
            "unit_suite": JobUpdateView._first(data.get("address[unit_suite]")),
            "city_name": JobUpdateView._first(data.get("address[city_name]")),
            "province_name": JobUpdateView._first(data.get("address[province_name]")),
            "country_name": JobUpdateView._first(data.get("address[country_name]")),
            "postal_code": JobUpdateView._first(data.get("address[postal_code]")),
        }

    @staticmethod
    def _extract_service_types_from_form(data):
        pattern = re.compile(r"^job_service_types\[(\d+)\]\[service_type_id\]$")
        items = []
        for k, v in data.items():
            m = pattern.match(k)
            if m:
                val = JobUpdateView._first(v)
                items.append((int(m.group(1)), val))
        if not items:
            return None
        items.sort(key=lambda x: x[0])
        out = []
        for _, val in items:
            if val is None:
                continue
            sval = str(val)
            if sval.isdigit():
                out.append({"service_type_id": int(sval)})
        return out

    @staticmethod
    def _resolve_address(user, data: dict) -> Address:
        required = ["country_name", "province_name", "city_name", "street_number", "street_name", "postal_code"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise ValueError(f"Address fields missing/empty: {', '.join(missing)}")
        country = Country.objects.filter(name__iexact=data["country_name"]).first()
        if not country:
            raise ValueError("Country not found. Seed countries first.")
        province = Province.objects.filter(name__iexact=data["province_name"], country=country).first()
        if not province:
            raise ValueError("Province not found for the given country.")
        city, _ = City.objects.get_or_create(name=data["city_name"], province=province)
        addr = Address(
            user=user,
            street_number=data["street_number"],
            street_name=data["street_name"],
            unit_suite=data.get("unit_suite") or None,
            city=city,
            postal_code=data["postal_code"],
        )
        addr.full_clean()
        addr.save()
        return addr

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        data = request.data.copy()

        start_date = data.pop("start_date", None)
        start_time = data.pop("start_time", None)

        address_payload = data.pop("address", None)
        if isinstance(address_payload, dict):
            addr_payload = address_payload
        else:
            addr_payload = self._extract_address_from_form(request.data)

        st_inputs = data.pop("job_service_types", None)
        if not isinstance(st_inputs, list):
            st_inputs = self._extract_service_types_from_form(request.data) if st_inputs is None else st_inputs

        if addr_payload:
            address = self._resolve_address(request.user, addr_payload)
            data["address"] = address.id

        new_start_at = None
        if start_date is not None or start_time is not None:
            new_start_at = self._make_start_at(start_date, start_time)

        target_service_id = data.get("service") or instance.service_id
        try:
            target_service_id = int(target_service_id)
        except (TypeError, ValueError):
            pass

        if st_inputs:
            st_ids = [int(x["service_type_id"]) for x in st_inputs if "service_type_id" in x]
            if st_ids:
                valid_count = ServiceType.objects.filter(id__in=st_ids, service_id=target_service_id).count()
                if valid_count != len(st_ids):
                    return Response(
                        {"job_service_types": "All service types must belong to the selected service."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        if new_start_at is not None:
            job.start_at = new_start_at
            job.save(update_fields=["start_at", "updated_at"])

        if st_inputs is not None:
            JobServiceType.objects.filter(job=job).delete()
            if st_inputs:
                JobServiceType.objects.bulk_create(
                    [JobServiceType(job=job, service_type_id=int(st["service_type_id"])) for st in st_inputs]
                )

        if hasattr(request.FILES, "getlist"):
            file_list = request.FILES.getlist("job_attachments")
            if file_list:
                old_files = list(JobAttachment.objects.filter(job=job))
                for att in old_files:
                    storage = att.attachment.storage
                    name = att.attachment.name
                    att.delete()
                    if name:
                        storage.delete(name)
                for f in file_list:
                    JobAttachment.objects.create(job=job, attachment=f)

        return Response(self.get_serializer(job).data, status=status.HTTP_200_OK)
    
class JobDeleteView(generics.DestroyAPIView):
    serializer_class = JobCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        for att in list(instance.attachments.all()):
            storage = att.attachment.storage
            name = att.attachment.name
            att.delete()
            if name:
                storage.delete(name)
        instance.delete()

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        if job.is_paid:
            return Response({"detail": "Paid jobs cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        if job.status in [JobStatus.IN_PROGRESS, JobStatus.COMPLETED]:
            return Response({"detail": "Jobs in progress or completed cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_destroy(job)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class JobListView(generics.ListAPIView):
    serializer_class = JobListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Job.objects.filter(user=self.request.user).select_related(
            "user",
            "professional",
            "professional__user",
            "address",
            "address__city",
            "address__city__province",
            "address__city__province__country",
            "service",
            "service__unit",
        ).prefetch_related(
            "service__categories",
            "job_service_types__service_type",
        )

        status_param = self.request.query_params.get("status")
        if status_param:
            statuses = [s.strip() for s in status_param.split(",") if s.strip()]
            valid = {c for c, _ in JobStatus.choices}
            statuses = [s for s in statuses if s in valid]
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        service_id = self.request.query_params.get("service")
        if service_id and service_id.isdigit():
            qs = qs.filter(service_id=int(service_id))

        st_param = self.request.query_params.get("service_types")
        if st_param:
            st_ids = [int(x) for x in st_param.split(",") if x.strip().isdigit()]
            if st_ids:
                qs = qs.filter(job_service_types__service_type_id__in=st_ids)

        city_name = self.request.query_params.get("city")
        if city_name:
            qs = qs.filter(address__city__name__iexact=city_name)

        province_param = self.request.query_params.get("province")
        if province_param:
            qs = qs.filter(
                Q(address__city__province__code__iexact=province_param) |
                Q(address__city__province__name__iexact=province_param)
            )

        is_paid_param = self.request.query_params.get("is_paid")
        if is_paid_param is not None:
            v = is_paid_param.lower()
            if v in {"true", "1", "yes"}:
                qs = qs.filter(is_paid=True)
            elif v in {"false", "0", "no"}:
                qs = qs.filter(is_paid=False)

        ordering = self.request.query_params.get("ordering")
        if ordering in {"created_at", "-created_at", "start_at", "-start_at", "total_price", "-total_price"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs.distinct()

class JobRetrieveView(generics.RetrieveAPIView):
    serializer_class = JobDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user).select_related(
            "user",
            "professional",
            "professional__user",
            "address",
            "address__city",
            "address__city__province",
            "address__city__province__country",
            "service",
            "service__unit",
        ).prefetch_related(
            "service__categories",
            "job_service_types__service_type",
        )

class PaymentSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        job_id = request.data.get('job_id')
        if not request.user.is_provider:
            return Response({"detail": "Only providers can initiate payment."}, status=status.HTTP_403_FORBIDDEN)
        try:
            job = Job.objects.get(id=job_id, user=request.user)
            remaining = job.outstanding_amount
            if remaining <= 0:
                return Response({"detail": "No outstanding balance."}, status=status.HTTP_400_BAD_REQUEST)
            remaining_q = remaining.quantize(Decimal("0.01"))
            total_price_cents = int(remaining_q * 100)
            customer = stripe.Customer.create(email=request.user.email or None)
            ephemeral_key = stripe.EphemeralKey.create(customer=customer['id'], stripe_version='2022-11-15')
            payment_intent = stripe.PaymentIntent.create(
                amount=total_price_cents,
                currency='cad',
                customer=customer['id'],
                automatic_payment_methods={'enabled': True},
                metadata={'job_id': job.id},
            )
            return Response(
                {
                    "paymentIntent": payment_intent.client_secret,
                    "ephemeralKey": ephemeral_key.secret,
                    "customer": customer['id'],
                    "publishableKey": settings.STRIPE_PUBLIC_KEY,
                    "payment_intent_id": payment_intent.id,
                    "amount": str(remaining_q),
                    "amountCents": total_price_cents,
                    "unit_price": str(job.unit_price),
                    "paid_units": str(job.paid_units),
                    "remaining_units": str(job.remaining_units),
                },
                status=status.HTTP_200_OK,
            )
        except Job.DoesNotExist:
            return Response({"detail": "Job not found or not owned by you."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PaymentSuccess(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get('payment_intent_id')
        job_id = request.data.get('job_id')
        amount_paid = request.data.get('amount_paid')

        if not payment_intent_id or not job_id or amount_paid is None:
            return Response(
                {"error": "payment_intent_id, job_id, and amount_paid are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not request.user.is_provider:
            return Response(
                {"detail": "Only providers can confirm payment."},
                status=status.HTTP_403_FORBIDDEN
            )

        job = get_object_or_404(Job, id=job_id, user=request.user)

        try:
            amt = Decimal(str(amount_paid)).quantize(Decimal("0.01"))
        except Exception:
            return Response({"error": "amount_paid must be a valid number."},
                            status=status.HTTP_400_BAD_REQUEST)
        if amt < Decimal("0.00"):
            return Response({"error": "amount_paid cannot be negative."},
                            status=status.HTTP_400_BAD_REQUEST)

        expected_total = job.total_price.quantize(Decimal("0.01"))

        field_name = None
        if hasattr(job, "paid_amount"):
            field_name = "paid_amount"
        elif hasattr(job, "collected_amount"):
            field_name = "collected_amount"
        elif hasattr(job, "amount_paid"):
            field_name = "amount_paid"
        else:
            field_name = "total_price"

        current_paid = getattr(job, field_name, Decimal("0.00")) or Decimal("0.00")
        try:
            current_paid = Decimal(str(current_paid)).quantize(Decimal("0.01"))
        except Exception:
            current_paid = Decimal("0.00")

        remaining = (expected_total - current_paid).quantize(Decimal("0.01"))
        applied = min(amt, max(remaining, Decimal("0.00")))
        new_paid = (current_paid + applied).quantize(Decimal("0.01"))

        setattr(job, field_name, new_paid)
        job.is_paid = new_paid >= expected_total
        job.stripe_session_id = str(payment_intent_id)

        update_fields = [field_name, 'is_paid', 'stripe_session_id', 'updated_at']
        job.save(update_fields=update_fields)

        return Response(
            {
                "message": "Payment processed.",
                "payment_intent_id": str(payment_intent_id),
                "applied_amount": str(applied),
                "submitted_amount": str(amt),
                "total_expected": str(expected_total),
                "total_paid": str(new_paid),
                "is_fully_paid": job.is_paid,
                "paid_units": str(job.paid_units),
                "remaining_units": str(job.remaining_units),
                "outstanding_amount": str(job.outstanding_amount),
                "unit_price": str(job.unit_price),
                "accumulator_field": field_name
            },
            status=status.HTTP_200_OK,
        )
        
class JobRateViewSet(viewsets.ModelViewSet):
    queryset = JobRate.objects.all()
    serializer_class = JobRateSerializer
    permission_classes = [permissions.IsAuthenticated]


# Job Unit Update Request Part
class JobUnitUpdateRequestCreateView(generics.CreateAPIView):
    serializer_class = JobUnitUpdateRequestCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class JobUnitUpdateRequestAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        req = get_object_or_404(JobUnitUpdateRequest.objects.select_related("job"), pk=pk)
        if req.job.user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if req.status != JobUnitUpdateRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be accepted."}, status=status.HTTP_400_BAD_REQUEST)
        req.accept()
        return Response({"id": req.id, "status": req.status, "new_unit_qty": str(req.new_unit_qty)}, status=status.HTTP_200_OK)


class JobUnitUpdateRequestRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        req = get_object_or_404(JobUnitUpdateRequest.objects.select_related("job"), pk=pk)
        if req.job.user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if req.status != JobUnitUpdateRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)
        req.status = JobUnitUpdateRequestStatus.REJECTED
        req.save(update_fields=["status", "updated_at"])
        return Response({"id": req.id, "status": req.status}, status=status.HTTP_200_OK)
    
class JobUnitUpdateRequestListForOwnerView(generics.ListAPIView):
    serializer_class = JobUnitUpdateRequestListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = JobUnitUpdateRequest.objects.filter(
            job__user=self.request.user
        ).select_related(
            "job", "professional", "professional__user"
        ).order_by("-created_at")

        status_param = self.request.query_params.get("status")
        if status_param:
            allowed = {c for c, _ in JobUnitUpdateRequestStatus.choices}
            statuses = [s for s in (x.strip() for x in status_param.split(",")) if s in allowed]
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        job_id = self.request.query_params.get("job")
        if job_id and job_id.isdigit():
            qs = qs.filter(job_id=int(job_id))

        return qs

class JobUnitUpdateRequestListForProfessionalView(generics.ListAPIView):
    serializer_class = JobUnitUpdateRequestListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, "professional_profile"):
            return JobUnitUpdateRequest.objects.none()

        qs = JobUnitUpdateRequest.objects.filter(
            professional=self.request.user.professional_profile
        ).select_related(
            "job", "professional", "professional__user"
        ).order_by("-created_at")

        status_param = self.request.query_params.get("status")
        if status_param:
            allowed = {c for c, _ in JobUnitUpdateRequestStatus.choices}
            statuses = [s for s in (x.strip() for x in status_param.split(",")) if s in allowed]
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        job_id = self.request.query_params.get("job")
        if job_id and job_id.isdigit():
            qs = qs.filter(job_id=int(job_id))

        return qs
    
class JobOfferListView(generics.ListAPIView):
    serializer_class = JobOfferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, "professional_profile"):
            return JobOffer.objects.none()
        prof = self.request.user.professional_profile
        qs = (
            JobOffer.objects
            .filter(professional=prof)
            .select_related("job", "job__service", "job__address__city__province")
            .order_by("-created_at")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            allowed = {c for c, _ in JobOfferStatus.choices}
            statuses = [s for s in (x.strip() for x in status_param.split(",")) if s in allowed]
            if statuses:
                qs = qs.filter(status__in=statuses)
        return qs


class JobOfferAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not hasattr(request.user, "professional_profile"):
            return Response({"detail": "Only professionals can accept offers."}, status=status.HTTP_403_FORBIDDEN)
        prof = request.user.professional_profile
        offer = get_object_or_404(
            JobOffer.objects.select_related("job"),
            pk=pk,
            professional=prof,
        )
        if offer.status not in [JobOfferStatus.SENT, JobOfferStatus.VIEWED]:
            return Response({"detail": "Only sent or viewed offers can be accepted."}, status=status.HTTP_400_BAD_REQUEST)
        job = offer.job
        if job.professional_id and job.professional_id != prof.id:
            return Response({"detail": "Job already assigned to another professional."}, status=status.HTTP_409_CONFLICT)
        if job.status not in [JobStatus.PENDING, JobStatus.IN_PROGRESS]:
            return Response({"detail": "Offer cannot be accepted for this job status."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            offer.accept()
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(JobOfferSerializer(offer).data, status=status.HTTP_200_OK)
    
# Professional Job List and Detail
class ProfessionalJobListView(generics.ListAPIView):
    serializer_class = JobListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, "professional_profile"):
            return Job.objects.none()

        qs = Job.objects.filter(
            professional=self.request.user.professional_profile
        ).select_related(
            "user",
            "professional",
            "professional__user",
            "address",
            "address__city",
            "address__city__province",
            "address__city__province__country",
            "service",
            "service__unit",
        ).prefetch_related(
            "service__categories",
            "job_service_types__service_type",
        )

        status_param = self.request.query_params.get("status")
        if status_param:
            statuses = [s.strip() for s in status_param.split(",") if s.strip()]
            valid = {c for c, _ in JobStatus.choices}
            statuses = [s for s in statuses if s in valid]
            if statuses:
                qs = qs.filter(status__in=statuses)

        service_id = self.request.query_params.get("service")
        if service_id:
            qs = qs.filter(service_id=service_id)

        st_param = self.request.query_params.get("service_types")
        if st_param:
            st_ids = [int(x) for x in st_param.split(",") if x.strip().isdigit()]
            if st_ids:
                qs = qs.filter(job_service_types__service_type_id__in=st_ids).distinct()

        city_name = self.request.query_params.get("city")
        if city_name:
            qs = qs.filter(address__city__name__iexact=city_name)

        province_param = self.request.query_params.get("province")
        if province_param:
            qs = qs.filter(
                Q(address__city__province__code__iexact=province_param) |
                Q(address__city__province__name__iexact=province_param)
            )

        is_paid_param = self.request.query_params.get("is_paid")
        if is_paid_param is not None:
            v = is_paid_param.lower()
            if v in {"true", "1", "yes"}:
                qs = qs.filter(is_paid=True)
            elif v in {"false", "0", "no"}:
                qs = qs.filter(is_paid=False)

        ordering = self.request.query_params.get("ordering")
        if ordering in {"created_at", "-created_at", "start_at", "-start_at", "total_price", "-total_price"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs


class ProfessionalJobRetrieveView(generics.RetrieveAPIView):
    serializer_class = JobDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, "professional_profile"):
            return Job.objects.none()

        return Job.objects.filter(
            professional=self.request.user.professional_profile
        ).select_related(
            "user",
            "professional",
            "professional__user",
            "address",
            "address__city",
            "address__city__province",
            "address__city__province__country",
            "service",
            "service__unit",
        ).prefetch_related(
            "service__categories",
            "job_service_types__service_type",
        )

# Job Attachment ServiceTypes and Address
class JobAttachmentListView(generics.ListAPIView):
    serializer_class = JobAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job = get_object_or_404(
            Job.objects.select_related("professional", "professional__user", "user"),
            pk=self.kwargs["pk"],
        )
        if not (job.user_id == self.request.user.id or (
            hasattr(self.request.user, "professional_profile") and
            job.professional_id == getattr(self.request.user.professional_profile, "id", None)
        )):
            return JobAttachment.objects.none()
        return JobAttachment.objects.filter(job=job).order_by("-uploaded_at")


class JobServiceTypeListView(generics.ListAPIView):
    serializer_class = JobServiceTypeItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job = get_object_or_404(
            Job.objects.select_related("professional", "professional__user", "user"),
            pk=self.kwargs["pk"],
        )
        if not (job.user_id == self.request.user.id or (
            hasattr(self.request.user, "professional_profile") and
            job.professional_id == getattr(self.request.user.professional_profile, "id", None)
        )):
            return JobServiceType.objects.none()
        return JobServiceType.objects.filter(job=job).select_related("service_type").order_by("service_type__title")
    

class JobAddressRetrieveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        job = get_object_or_404(
            Job.objects.select_related(
                "user",
                "professional",
                "professional__user",
                "address",
                "address__city",
                "address__city__province",
                "address__city__province__country",
            ),
            pk=pk,
        )
        is_owner = job.user_id == request.user.id
        is_assigned_pro = hasattr(request.user, "professional_profile") and job.professional_id == getattr(request.user.professional_profile, "id", None)
        if not (is_owner or is_assigned_pro):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        data = JobAddressSerializer(job.address).data
        return Response(data, status=status.HTTP_200_OK)