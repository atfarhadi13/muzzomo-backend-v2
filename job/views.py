import re

import stripe

from datetime import datetime, date, time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError

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

# ---------- Shared helpers ----------

def _decimal(val, field_name="value"):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number.")


def _is_truthy(v: str) -> bool | None:
    if v is None:
        return None
    s = v.lower().strip()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


# ---------- JobCreateView ----------

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
            try:
                return date.fromisoformat(val)
            except ValueError:
                raise ValueError("start_date must be ISO format (YYYY-MM-DD).")
        raise ValueError("start_date must be a date or ISO date string.")

    @staticmethod
    def _coerce_time(val):
        if not val:
            return None
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            try:
                return time.fromisoformat(val)
            except ValueError:
                raise ValueError("start_time must be ISO format (HH:MM[:SS]).")
        raise ValueError("start_time must be a time or ISO time string.")

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
            "address[street_number]", "address[street_name]", "address[unit_suite]",
            "address[city_name]", "address[province_name]", "address[country_name]",
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
        out = []
        for _, val in items:
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
        try:
            addr.full_clean()
            addr.save()
        except DjangoValidationError as e:
            raise ValueError(e.message_dict if hasattr(e, "message_dict") else e.messages)
        except IntegrityError:
            raise ValueError("Could not save address. Please try again.")
        return addr

    @staticmethod
    def _create_job_offers(job):
        try:
            city = job.address.city
            service = job.service
            start_at = job.start_at

            pros_in_city = Professional.objects.filter(
                user__addresses__city=city,
                verification_status='approved',
                is_verified=True
            ).distinct()

            pros_with_service = ProfessionalService.objects.filter(
                service=service,
                professional__in=pros_in_city
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
        except Exception:
            # Offers failing should not break job creation
            return 0

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        user = request.user

        try:
            # Address payload (supports JSON body or multipart form keys)
            address_payload = data.get("address")
            addr_payload = address_payload if isinstance(address_payload, dict) else (self._extract_address_from_form(data) or {})

            # Service types (supports JSON array or indexed form keys)
            st_inputs = data.get("job_service_types")
            if not isinstance(st_inputs, list):
                st_inputs = self._extract_service_types_from_form(data) or []

            # Schedule
            start_date = data.get("start_date")
            start_time = data.get("start_time")

            # Resolve address to ID for serializer
            address = self._resolve_address(user, addr_payload)
            data["address"] = address.id

            # Validate and create job
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            job = serializer.save(
                user=user,
                start_at=self._make_start_at(start_date, start_time),
            )

            # Attach service types
            if st_inputs:
                st_ids = [int(x["service_type_id"]) for x in st_inputs]
                JobServiceType.objects.bulk_create(
                    [JobServiceType(job=job, service_type_id=st_id) for st_id in st_ids]
                )

            # Attach files (ignore single file errors so one bad file doesn’t kill the request)
            file_list = request.FILES.getlist("job_attachments") if hasattr(request.FILES, "getlist") else []
            for f in file_list:
                try:
                    JobAttachment.objects.create(job=job, attachment=f)
                except Exception:
                    continue

            # Fire offers (best-effort)
            offer_count = self._create_job_offers(job)

            return Response(
                {"job_id": job.id, "message": f"Job created successfully. Offered to {offer_count} professionals."},
                status=status.HTTP_201_CREATED,
            )

        except (ValueError, DjangoValidationError) as e:
            transaction.set_rollback(True)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"detail": "Unexpected error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------- JobUpdateView ----------

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
            try:
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError("start_date must be ISO format (YYYY-MM-DD).")
        raise ValueError("start_date must be a date or ISO date string.")

    @staticmethod
    def _coerce_time(val):
        v = JobUpdateView._first(val)
        if not v:
            return None
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            try:
                return time.fromisoformat(v)
            except ValueError:
                raise ValueError("start_time must be ISO format (HH:MM[:SS]).")
        raise ValueError("start_time must be a time or ISO time string.")

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
            "address[street_number]", "address[street_name]", "address[unit_suite]",
            "address[city_name]", "address[province_name]", "address[country_name]",
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
        try:
            addr.full_clean()
            addr.save()
        except DjangoValidationError as e:
            raise ValueError(e.message_dict if hasattr(e, "message_dict") else e.messages)
        except IntegrityError:
            raise ValueError("Could not save address. Please try again.")
        return addr

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        data = request.data.copy()

        try:
            start_date = data.pop("start_date", None)
            start_time = data.pop("start_time", None)

            address_payload = data.pop("address", None)
            addr_payload = address_payload if isinstance(address_payload, dict) else self._extract_address_from_form(request.data)

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
                st_ids = []
                for x in st_inputs:
                    try:
                        st_ids.append(int(x["service_type_id"]))
                    except (KeyError, TypeError, ValueError):
                        return Response({"job_service_types": "Invalid service_type_id."},
                                        status=status.HTTP_400_BAD_REQUEST)
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

            # Replace attachments only if new ones are provided
            if hasattr(request.FILES, "getlist"):
                file_list = request.FILES.getlist("job_attachments")
                if file_list:
                    old_files = list(JobAttachment.objects.filter(job=job))
                    for att in old_files:
                        try:
                            storage = att.attachment.storage
                            name = att.attachment.name
                            att.delete()
                            if name:
                                try:
                                    storage.delete(name)
                                except Exception:
                                    pass
                        except Exception:
                            continue
                    for f in file_list:
                        try:
                            JobAttachment.objects.create(job=job, attachment=f)
                        except Exception:
                            continue

            return Response(self.get_serializer(job).data, status=status.HTTP_200_OK)

        except (ValueError, DjangoValidationError) as e:
            transaction.set_rollback(True)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"detail": "Unexpected error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ---------- JobDeleteView ----------

class JobDeleteView(generics.DestroyAPIView):
    serializer_class = JobCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        # Delete attachments defensively
        for att in list(instance.attachments.all()):
            try:
                storage = att.attachment.storage
                name = att.attachment.name
                att.delete()
                if name:
                    try:
                        storage.delete(name)
                    except Exception:
                        pass
            except Exception:
                continue
        instance.delete()

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        if job.is_paid:
            return Response({"detail": "Paid jobs cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        if job.status in [JobStatus.IN_PROGRESS, JobStatus.COMPLETED]:
            return Response({"detail": "Jobs in progress or completed cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            self.perform_destroy(job)
        except Exception as e:
            return Response({"detail": "Could not delete job.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- JobListView ----------

class JobListView(generics.ListAPIView):
    serializer_class = JobListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Job.objects.filter(user=self.request.user).select_related(
            "user",
            "professional", "professional__user",
            "address", "address__city", "address__city__province", "address__city__province__country",
            "service", "service__unit",
        ).prefetch_related(
            "service__categories",
            "job_service_types__service_type",
        )

        # status
        status_param = self.request.query_params.get("status")
        if status_param:
            statuses = [s.strip() for s in status_param.split(",") if s.strip()]
            valid = {c for c, _ in JobStatus.choices}
            statuses = [s for s in statuses if s in valid]
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        # service
        service_id = self.request.query_params.get("service")
        if service_id and str(service_id).isdigit():
            qs = qs.filter(service_id=int(service_id))

        # service types
        st_param = self.request.query_params.get("service_types")
        if st_param:
            st_ids = [int(x) for x in st_param.split(",") if x.strip().isdigit()]
            if st_ids:
                qs = qs.filter(job_service_types__service_type_id__in=st_ids)

        # city
        city_name = self.request.query_params.get("city")
        if city_name:
            qs = qs.filter(address__city__name__iexact=city_name)

        # province
        province_param = self.request.query_params.get("province")
        if province_param:
            qs = qs.filter(
                Q(address__city__province__code__iexact=province_param) |
                Q(address__city__province__name__iexact=province_param)
            )

        # is_paid
        is_paid_param = self.request.query_params.get("is_paid")
        tf = _is_truthy(is_paid_param)
        if tf is True:
            qs = qs.filter(is_paid=True)
        elif tf is False:
            qs = qs.filter(is_paid=False)

        # ordering
        ordering = self.request.query_params.get("ordering")
        if ordering in {"created_at", "-created_at", "start_at", "-start_at", "total_price", "-total_price"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs.distinct()


# ---------- JobRetrieveView ----------

class JobRetrieveView(generics.RetrieveAPIView):
    serializer_class = JobDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user).select_related(
            "user",
            "professional", "professional__user",
            "address", "address__city", "address__city__province", "address__city__province__country",
            "service", "service__unit",
        ).prefetch_related(
            "service__categories",
            "job_service_types__service_type",
        )

class PaymentSheetView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        job_id = request.data.get("job_id")
        if not request.user.is_provider:
            return Response({"detail": "Only providers can initiate payment."}, status=status.HTTP_403_FORBIDDEN)
        if not job_id:
            return Response({"detail": "job_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = Job.objects.get(id=job_id, user=request.user)
        except Job.DoesNotExist:
            return Response({"detail": "Job not found or not owned by you."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Ensure total matches latest service * quantity before computing outstanding
            computed_total = job.computed_total_price
            if job.total_price != computed_total:
                job.total_price = computed_total
                # model.save() recalculates is_paid; include is_paid in update_fields is optional
                job.save(update_fields=["total_price", "updated_at"])

            remaining = job.outstanding_amount
            if remaining <= 0:
                return Response({"detail": "No outstanding balance."}, status=status.HTTP_400_BAD_REQUEST)

            remaining_q = remaining.quantize(Decimal("0.01"))
            amount_cents = int(remaining_q * 100)

            customer = stripe.Customer.create(email=request.user.email or None)
            ephemeral_key = stripe.EphemeralKey.create(customer=customer["id"], stripe_version="2022-11-15")
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="cad",
                customer=customer["id"],
                automatic_payment_methods={"enabled": True},
                metadata={"job_id": job.id},
                idempotency_key=f"job:{job.id}:remaining:{amount_cents}"  # <- add
            )

            return Response(
                {
                    "paymentIntent": payment_intent.client_secret,
                    "ephemeralKey": ephemeral_key.secret,
                    "customer": customer["id"],
                    "publishableKey": settings.STRIPE_PUBLIC_KEY,
                    "payment_intent_id": payment_intent.id,
                    "amount": str(remaining_q),
                    "amountCents": amount_cents,
                    "unit_price": str(job.unit_price),
                    "paid_units": str(job.paid_units),
                    "remaining_units": str(job.remaining_units),
                },
                status=status.HTTP_200_OK,
            )
        except stripe.error.StripeError as e:
            return Response({"detail": "Stripe error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except (InvalidOperation, ValueError) as e:
            return Response({"detail": "Invalid numeric computation.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "Unexpected error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentSuccess(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get("payment_intent_id")
        job_id = request.data.get("job_id")
        amount_paid = request.data.get("amount_paid")

        if not payment_intent_id or not job_id or amount_paid is None:
            return Response(
                {"error": "payment_intent_id, job_id, and amount_paid are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.is_provider:
            return Response({"detail": "Only providers can confirm payment."}, status=status.HTTP_403_FORBIDDEN)

        job = get_object_or_404(Job, id=job_id, user=request.user)

        try:
            amt = Decimal(str(amount_paid)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            return Response({"error": "amount_paid must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)
        if amt < Decimal("0.00"):
            return Response({"error": "amount_paid cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Refresh total before applying payment in case quantity/service changed
            computed_total = job.computed_total_price
            if job.total_price != computed_total:
                job.total_price = computed_total
                job.save(update_fields=["total_price", "updated_at"])

            current = (job.paid_amount or Decimal("0.00")).quantize(Decimal("0.01"))
            expected = (job.total_price or Decimal("0.00")).quantize(Decimal("0.01"))
            remaining = (expected - current)
            if remaining <= 0:
                # Already fully paid; idempotent success response
                return Response(
                    {
                        "message": "Already fully paid.",
                        "payment_intent_id": str(payment_intent_id),
                        "applied_amount": "0.00",
                        "submitted_amount": str(amt),
                        "total_expected": str(expected),
                        "total_paid": str(current),
                        "is_fully_paid": True,
                        "paid_units": str(job.paid_units),
                        "remaining_units": str(job.remaining_units),
                        "outstanding_amount": "0.00",
                        "unit_price": str(job.unit_price),
                    },
                    status=status.HTTP_200_OK,
                )

            applied = min(max(remaining, Decimal("0.00")), amt)

            job.paid_amount = (current + applied).quantize(Decimal("0.01"))
            job.stripe_session_id = str(payment_intent_id)
            # model.save() recomputes is_paid
            job.save(update_fields=["paid_amount", "stripe_session_id", "updated_at"])

            return Response(
                {
                    "message": "Payment processed.",
                    "payment_intent_id": str(payment_intent_id),
                    "applied_amount": str(applied),
                    "submitted_amount": str(amt),
                    "total_expected": str(expected),
                    "total_paid": str(job.paid_amount),
                    "is_fully_paid": job.is_paid,
                    "paid_units": str(job.paid_units),
                    "remaining_units": str(job.remaining_units),
                    "outstanding_amount": str(job.outstanding_amount),
                    "unit_price": str(job.unit_price),
                },
                status=status.HTTP_200_OK,
            )
        except (InvalidOperation, ValueError) as e:
            return Response({"error": "Invalid numeric computation.", "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": "Unexpected error.", "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class JobRateViewSet(viewsets.ModelViewSet):
    serializer_class = JobRateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show ratings for the current user's jobs
        return JobRate.objects.select_related("job").filter(job__user=self.request.user)

    def perform_create(self, serializer):
        # Serializer already validates ownership & completion/paid rules
        serializer.save()

    def perform_update(self, serializer):
        # Keep same validations on update
        serializer.save()


# ----- Job Unit Update Requests -----

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
        req = get_object_or_404(
            JobUnitUpdateRequest.objects.select_related("job"),
            pk=pk
        )
        if req.job.user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if req.status != JobUnitUpdateRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be accepted."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req.accept()
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"detail": "Could not accept request.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"id": req.id, "status": req.status, "new_unit_qty": str(req.new_unit_qty)},
            status=status.HTTP_200_OK
        )


class JobUnitUpdateRequestRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        req = get_object_or_404(
            JobUnitUpdateRequest.objects.select_related("job"),
            pk=pk
        )
        if req.job.user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if req.status != JobUnitUpdateRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req.status = JobUnitUpdateRequestStatus.REJECTED
            req.save(update_fields=["status", "updated_at"])
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"detail": "Could not reject request.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
        if job_id and str(job_id).isdigit():
            qs = qs.filter(job_id=int(job_id))

        return qs


class JobUnitUpdateRequestListForProfessionalView(generics.ListAPIView):
    serializer_class = JobUnitUpdateRequestListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            return JobUnitUpdateRequest.objects.none()

        qs = JobUnitUpdateRequest.objects.filter(
            professional=prof
        ).select_related(
            "job", "professional", "professional__user"
        ).order_by("-created_at")

        status_param = self.request.query_params.get("status")
        if status_param:
            allowed = {c for c, _ in JobUnitUpdateRequestStatus.choices}
            statuses = [s for s in (x.strip() for x in status_param.split(",")) if s in allowed]
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        job_id = self.request.query_params.get("job")
        if job_id and str(job_id).isdigit():
            qs = qs.filter(job_id=int(job_id))

        return qs
    

class JobOfferListView(generics.ListAPIView):
    serializer_class = JobOfferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            # No professional profile => no access
            return JobOffer.objects.none()

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
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        return qs


class JobOfferAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        prof = getattr(request.user, "professional_profile", None)
        if not prof:
            return Response({"detail": "Only professionals can accept offers."}, status=status.HTTP_403_FORBIDDEN)

        offer = get_object_or_404(
            JobOffer.objects.select_related("job"),
            pk=pk,
            professional=prof,
        )

        if offer.status not in {JobOfferStatus.SENT, JobOfferStatus.VIEWED}:
            return Response({"detail": "Only sent or viewed offers can be accepted."}, status=status.HTTP_400_BAD_REQUEST)

        job = offer.job
        if job.professional_id and job.professional_id != prof.id:
            return Response({"detail": "Job already assigned to another professional."}, status=status.HTTP_409_CONFLICT)

        if job.status not in {JobStatus.PENDING, JobStatus.IN_PROGRESS}:
            return Response({"detail": "Offer cannot be accepted for this job status."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            offer.accept()  # assumes your model method handles assignment & state updates atomically
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error accepting offer.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            transaction.set_rollback(True)
            return Response({"detail": "Could not accept offer.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(JobOfferSerializer(offer).data, status=status.HTTP_200_OK)


class ProfessionalJobListView(generics.ListAPIView):
    serializer_class = JobListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            return Job.objects.none()

        qs = (
            Job.objects.filter(professional=prof)
            .select_related(
                "user",
                "professional",
                "professional__user",
                "address",
                "address__city",
                "address__city__province",
                "address__city__province__country",
                "service",
                "service__unit",
            )
            .prefetch_related(
                "service__categories",
                "job_service_types__service_type",
            )
        )

        qparams = self.request.query_params

        status_param = qparams.get("status")
        if status_param:
            valid = {c for c, _ in JobStatus.choices}
            statuses = [s for s in (x.strip() for x in status_param.split(",")) if s in valid]
            qs = qs.filter(status__in=statuses) if statuses else qs.none()

        service_id = qparams.get("service")
        if service_id and str(service_id).isdigit():
            qs = qs.filter(service_id=int(service_id))

        st_param = qparams.get("service_types")
        if st_param:
            st_ids = [int(x) for x in st_param.split(",") if x.strip().isdigit()]
            if st_ids:
                qs = qs.filter(job_service_types__service_type_id__in=st_ids)

        city_name = qparams.get("city")
        if city_name:
            qs = qs.filter(address__city__name__iexact=city_name)

        province_param = qparams.get("province")
        if province_param:
            qs = qs.filter(
                Q(address__city__province__code__iexact=province_param) |
                Q(address__city__province__name__iexact=province_param)
            )

        is_paid_param = qparams.get("is_paid")
        if is_paid_param is not None:
            v = (is_paid_param or "").lower()
            if v in {"true", "1", "yes"}:
                qs = qs.filter(is_paid=True)
            elif v in {"false", "0", "no"}:
                qs = qs.filter(is_paid=False)

        ordering = qparams.get("ordering")
        if ordering in {"created_at", "-created_at", "start_at", "-start_at", "total_price", "-total_price"}:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs.distinct()


class ProfessionalJobRetrieveView(generics.RetrieveAPIView):
    serializer_class = JobDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        prof = getattr(self.request.user, "professional_profile", None)
        if not prof:
            return Job.objects.none()

        return (
            Job.objects.filter(professional=prof)
            .select_related(
                "user",
                "professional",
                "professional__user",
                "address",
                "address__city",
                "address__city__province",
                "address__city__province__country",
                "service",
                "service__unit",
            )
            .prefetch_related(
                "service__categories",
                "job_service_types__service_type",
            )
        )


class JobAttachmentListView(generics.ListAPIView):
    serializer_class = JobAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job = get_object_or_404(
            Job.objects.select_related("professional", "professional__user", "user"),
            pk=self.kwargs["pk"],
        )
        is_owner = job.user_id == self.request.user.id
        is_assigned_pro = (
            hasattr(self.request.user, "professional_profile") and
            job.professional_id == getattr(self.request.user.professional_profile, "id", None)
        )
        if not (is_owner or is_assigned_pro):
            # Explicitly deny instead of silently returning none
            raise PermissionError("Not allowed to view this job's attachments.")

        return JobAttachment.objects.filter(job=job).order_by("-uploaded_at")

    def handle_exception(self, exc):
        if isinstance(exc, PermissionError):
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return super().handle_exception(exc)


class JobServiceTypeListView(generics.ListAPIView):
    serializer_class = JobServiceTypeItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job = get_object_or_404(
            Job.objects.select_related("professional", "professional__user", "user"),
            pk=self.kwargs["pk"],
        )
        is_owner = job.user_id == self.request.user.id
        is_assigned_pro = (
            hasattr(self.request.user, "professional_profile") and
            job.professional_id == getattr(self.request.user.professional_profile, "id", None)
        )
        if not (is_owner or is_assigned_pro):
            raise PermissionError("Not allowed to view this job's service types.")

        return (
            JobServiceType.objects
            .filter(job=job)
            .select_related("service_type")
            .order_by("service_type__title")
        )

    def handle_exception(self, exc):
        if isinstance(exc, PermissionError):
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return super().handle_exception(exc)


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
        is_assigned_pro = (
            hasattr(request.user, "professional_profile") and
            job.professional_id == getattr(request.user.professional_profile, "id", None)
        )
        if not (is_owner or is_assigned_pro):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        data = JobAddressSerializer(job.address).data
        return Response(data, status=status.HTTP_200_OK)


class JobCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        job = get_object_or_404(Job.objects.select_for_update(), pk=pk, user=request.user)

        if job.status == JobStatus.COMPLETED:
            return Response({"detail": "Job already completed."}, status=status.HTTP_400_BAD_REQUEST)
        if job.status == JobStatus.CANCELLED:
            return Response({"detail": "Cancelled job cannot be completed."}, status=status.HTTP_400_BAD_REQUEST)
        if not job.professional_id:
            return Response({"detail": "Job has no assigned professional."}, status=status.HTTP_400_BAD_REQUEST)
        if job.status != JobStatus.IN_PROGRESS:
            return Response({"detail": "Only in-progress jobs can be completed."}, status=status.HTTP_400_BAD_REQUEST)

        # Payment gate
        if job.outstanding_amount > Decimal("0.00"):
            return Response(
                {
                    "detail": "Payment required before completion.",
                    "outstanding_amount": str(job.outstanding_amount),
                    "total_price": str(job.total_price),
                    "paid_amount": str(job.paid_amount),
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        job.completed_date = timezone.now()
        job.status = JobStatus.COMPLETED
        if not job.is_paid:
            job.is_paid = True

        try:
            job.save(update_fields=["completed_date", "status", "is_paid", "updated_at"])
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": job.id,
                "status": job.status,
                "completed_date": job.completed_date,
                "total_price": str(job.total_price),
                "paid_amount": str(job.paid_amount),
                "outstanding_amount": str(job.outstanding_amount),
            },
            status=status.HTTP_200_OK,
        )


class JobCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        job = get_object_or_404(Job.objects.select_for_update(), pk=pk, user=request.user)

        if job.status == JobStatus.CANCELLED:
            return Response({"detail": "Job already cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        if job.status == JobStatus.COMPLETED:
            return Response({"detail": "Completed job cannot be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        if job.status == JobStatus.IN_PROGRESS:
            return Response({"detail": "In-progress job cannot be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        if job.professional_id:
            return Response({"detail": "Cannot cancel a job that has an assigned professional."}, status=status.HTTP_400_BAD_REQUEST)
        if (job.paid_amount or Decimal("0.00")) > Decimal("0.00"):
            return Response({"detail": "Job with payments cannot be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job.status = JobStatus.CANCELLED
            job.save(update_fields=["status", "updated_at"])
        except IntegrityError as e:
            transaction.set_rollback(True)
            return Response({"detail": "Database error.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"id": job.id, "status": job.status}, status=status.HTTP_200_OK)