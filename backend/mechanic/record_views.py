from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsMechanic
from diagnosis.models import (
    DiagnosisSession, MechanicInspection, MechanicOutcomeAudit,
    MechanicRepairOutcome,
)
from garage.models import Car

from .record_serializers import (
    MechanicCarSerializer, MechanicInspectionSerializer,
    MechanicOutcomeAuditSerializer, MechanicOutcomeSerializer,
    MechanicRecordSerializer,
)


def mechanic_records(user):
    return (DiagnosisSession.objects.filter(
        Q(mechanic_reporter=user) | Q(outcome__mechanic=user))
        .select_related("car__car_model__car_make", "obd_code", "category",
                        "outcome__mechanic", "mechanic_outcome__mechanic",
                        "mechanic_outcome__actual_cause")
        .prefetch_related(
            "answers__question", "answers__option", "results",
            "session_symptoms__symptom",
            "mechanic_inspections__mechanic",
            "mechanic_inspections__suspected_cause",
            "mechanic_outcome__audit_entries__mechanic")
        .distinct().order_by("-started_at"))


def get_mechanic_record(user, pk):
    return get_object_or_404(mechanic_records(user), pk=pk)


def _outcome_snapshot(outcome):
    return dict(MechanicOutcomeSerializer(outcome).data)


def _record_audit(outcome, mechanic, action):
    MechanicOutcomeAudit.objects.create(
        outcome=outcome, mechanic=mechanic, action=action,
        snapshot=_outcome_snapshot(outcome))


class MechanicVehicleListView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def get(self, request):
        vehicles = Car.objects.filter(user=request.user).select_related(
            "car_model__car_make").order_by("id")
        return Response(MechanicCarSerializer(vehicles, many=True).data)


class MechanicRecordListView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def get(self, request):
        records = mechanic_records(request.user)
        search = request.query_params.get("q", "").strip()
        if search:
            records = records.filter(
                Q(free_text__icontains=search)
                | Q(car__nickname__icontains=search)
                | Q(car__car_model__name__icontains=search)
                | Q(obd_code__code__icontains=search)
                | Q(obd_code__description__icontains=search))
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            if status_filter not in DiagnosisSession.Status.values:
                raise ValidationError({"status": "Choose a valid diagnosis status."})
            records = records.filter(status=status_filter)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(records, request, view=self)
        response = paginator.get_paginated_response(
            MechanicRecordSerializer(page, many=True).data)
        response.data["summary"] = {
            "total": records.count(),
            "open": records.filter(
                status=DiagnosisSession.Status.IN_PROGRESS).count(),
            "completed": records.filter(
                status=DiagnosisSession.Status.COMPLETED).count(),
            "repair_completed": records.filter(
                mechanic_outcome__repair_status=(
                    MechanicRepairOutcome.RepairStatus.COMPLETED),
                mechanic_outcome__submitted_at__isnull=False).count(),
            "outcome_drafts": records.filter(
                mechanic_outcome__submitted_at__isnull=True,
                mechanic_outcome__mechanic=request.user).count(),
        }
        return response


class MechanicRecordDetailView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def get(self, request, pk):
        return Response(MechanicRecordSerializer(
            get_mechanic_record(request.user, pk)).data)


class MechanicInspectionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def post(self, request, pk):
        session = get_mechanic_record(request.user, pk)
        serializer = MechanicInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspection = serializer.save(session=session, mechanic=request.user)
        return Response(MechanicInspectionSerializer(inspection).data, status=201)


class MechanicInspectionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def patch(self, request, pk, inspection_id):
        session = get_mechanic_record(request.user, pk)
        inspection = get_object_or_404(
            MechanicInspection, pk=inspection_id, session=session,
            mechanic=request.user)
        if inspection.status != MechanicInspection.Status.DRAFT:
            raise ValidationError({"status": "Submitted inspections cannot be edited."})
        serializer = MechanicInspectionSerializer(
            inspection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(MechanicInspectionSerializer(serializer.save()).data)


class MechanicInspectionSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def post(self, request, pk, inspection_id):
        session = get_mechanic_record(request.user, pk)
        inspection = get_object_or_404(
            MechanicInspection, pk=inspection_id, session=session,
            mechanic=request.user)
        if inspection.status != MechanicInspection.Status.DRAFT:
            raise ValidationError({"status": "This inspection has already been submitted."})
        errors = {}
        if not inspection.findings.strip():
            errors["findings"] = "Add inspection findings before submitting."
        if not inspection.tests_performed.strip():
            errors["tests_performed"] = "Record at least one test or check performed."
        if errors:
            raise serializers.ValidationError(errors)
        inspection.status = MechanicInspection.Status.SUBMITTED
        inspection.submitted_at = timezone.now()
        inspection.save(update_fields=["status", "submitted_at", "updated_at"])
        return Response(MechanicInspectionSerializer(inspection).data)


class MechanicOutcomeView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def get(self, request, pk):
        session = get_mechanic_record(request.user, pk)
        outcome = getattr(session, "mechanic_outcome", None)
        if outcome is None:
            return Response(None)
        return Response({
            "outcome": MechanicOutcomeSerializer(outcome).data,
            "history": MechanicOutcomeAuditSerializer(
                outcome.audit_entries.select_related("mechanic"), many=True).data,
        })

    def post(self, request, pk):
        session = get_mechanic_record(request.user, pk)
        return self._save(request, session, partial=False)

    def patch(self, request, pk):
        session = get_mechanic_record(request.user, pk)
        return self._save(request, session, partial=True)

    @transaction.atomic
    def _save(self, request, session, partial):
        session = DiagnosisSession.objects.select_for_update().get(pk=session.pk)
        assigned_outcome = getattr(session, "outcome", None)
        if assigned_outcome and assigned_outcome.mechanic_id not in (
                None, request.user.pk):
            raise PermissionDenied("This record is assigned to another mechanic.")
        outcome = MechanicRepairOutcome.objects.select_for_update().filter(
            session=session).first()
        if outcome and outcome.mechanic_id != request.user.pk:
            raise PermissionDenied("This outcome is attributed to another mechanic.")
        if outcome and not partial:
            return Response({"detail": "An outcome already exists; update it instead."},
                            status=409)
        if not outcome and partial:
            raise ValidationError({"outcome": "Save a draft before updating it."})
        previous = _outcome_snapshot(outcome) if outcome else None
        serializer = MechanicOutcomeSerializer(
            outcome, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        outcome = serializer.save(session=session, mechanic=request.user)
        was_final = bool(outcome.submitted_at)
        action = "corrected" if was_final else "draft_saved"
        if previous is None:
            action = "draft_created"
        if was_final:
            outcome.submitted_at = None
            outcome.save(update_fields=["submitted_at"])
        _record_audit(outcome, request.user, action)
        return Response({
            "outcome": MechanicOutcomeSerializer(outcome).data,
            "history": MechanicOutcomeAuditSerializer(
                outcome.audit_entries.select_related("mechanic"), many=True).data,
        }, status=201 if previous is None else 200)


class MechanicOutcomeSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    @transaction.atomic
    def post(self, request, pk):
        session = get_mechanic_record(request.user, pk)
        assigned_outcome = getattr(session, "outcome", None)
        if assigned_outcome and assigned_outcome.mechanic_id not in (
                None, request.user.pk):
            raise PermissionDenied("This record is assigned to another mechanic.")
        outcome = MechanicRepairOutcome.objects.select_for_update().filter(
            session=session).first()
        if outcome is None:
            raise ValidationError({"outcome": "Save the repair outcome before finalizing it."})
        if outcome.mechanic_id != request.user.pk:
            raise PermissionDenied("Only the mechanic who recorded this outcome can submit it.")
        if outcome.submitted_at:
            return Response({"detail": "This outcome has already been submitted."},
                            status=409)
        errors = {}
        if not outcome.actual_cause_id and not outcome.actual_cause_text.strip():
            errors["actual_cause"] = "Record a confirmed cause or explain the unresolved finding."
        if not outcome.repair_status:
            errors["repair_status"] = "Select the repair status."
        if not outcome.result_status:
            errors["result_status"] = "Select the result or next diagnostic step."
        if (outcome.repair_status == MechanicRepairOutcome.RepairStatus.COMPLETED
                and not outcome.repair_actions.strip()):
            errors["repair_actions"] = "Describe the repair performed."
        if errors:
            raise ValidationError(errors)
        outcome.submitted_at = timezone.now()
        outcome.save(update_fields=["submitted_at"])
        _record_audit(outcome, request.user, "submitted")
        return Response({
            "outcome": MechanicOutcomeSerializer(outcome).data,
            "history": MechanicOutcomeAuditSerializer(
                outcome.audit_entries.select_related("mechanic"), many=True).data,
        })
