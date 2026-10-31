from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from rest_framework import filters, generics, throttling, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from accounts.mixins import ParamFilterMixin
from accounts.permissions import (IsAdminRole, IsReviewerOrAdmin,
                                  ReadOnlyOrReviewer, is_staff_role)
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .importer import ImportErrorInFile, import_flow
from .api import DraftContentResponseMixin
from .models import (AnswerOption, Cause, CauseSymptomLink, ContentRevision, ContentReview,
                     ObdCode, Question, RepairCost, SelfCheck, Status, Symptom,
                     SymptomCategory, WarningLight)
from .serializers import (AnswerOptionSerializer, CauseSerializer,
                          CauseSymptomLinkSerializer, ContentReviewSerializer,
                          ObdCodeSerializer, QuestionSerializer,
                          RepairCostSerializer, SelfCheckSerializer,
                          SymptomCategorySerializer, SymptomSerializer,
                          WarningLightSerializer, PublicObdCodeSerializer)
from .services import workflow


class KnowledgeViewSet(DraftContentResponseMixin, ParamFilterMixin,
                       viewsets.ModelViewSet):
    """Anyone reads; reviewers/admins write. Normal users only see content
    whose status is 'published' (public_filter narrows child tables)."""
    permission_classes = [ReadOnlyOrReviewer]
    filter_backends = [filters.SearchFilter]
    public_filter = {}

    def get_queryset(self):
        qs = super().get_queryset()
        if is_staff_role(self.request.user) or not self.public_filter:
            return qs
        return qs.filter(**self.public_filter)


class GovernedWritePermission(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(
            request.user.is_authenticated and
            (is_staff_role(request.user) or request.user.role == "mechanic")
        )


def _revision_value(value):
    if hasattr(value, "pk"):
        return value.pk
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if hasattr(item, "pk"):
                result[f"{key}_id"] = item.pk
            else:
                result[key] = _revision_value(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_revision_value(item) for item in value]
    return value


class GovernedViewSet(KnowledgeViewSet):
    """Adds the draft -> submitted -> review -> approved -> published flow."""
    public_filter = {}
    permission_classes = [GovernedWritePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_staff_role(self.request.user):
            return queryset
        queryset = queryset.visible()
        if queryset.model is Question:
            return queryset.filter(symptom__in=Symptom.objects.visible())
        if queryset.model in (SelfCheck, RepairCost):
            return queryset.filter(cause__in=Cause.objects.visible())
        return queryset

    def perform_create(self, serializer):
        if serializer.Meta.model in (SelfCheck, RepairCost):
            cause = serializer.validated_data.get("cause")
            if cause and cause.status in (Status.APPROVED, Status.PUBLISHED):
                from rest_framework.exceptions import ValidationError as APIValidationError
                raise APIValidationError(
                    "Self-checks and costs on approved causes belong in a cause revision.")
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if (isinstance(serializer.instance, (SelfCheck, RepairCost)) and
                serializer.instance.cause.status in (Status.APPROVED, Status.PUBLISHED)):
            from rest_framework.exceptions import ValidationError as APIValidationError
            raise APIValidationError(
                "Self-checks and costs on approved causes belong in a cause revision.")
        if serializer.instance.status not in (Status.DRAFT, Status.AI_DRAFT):
            from rest_framework.exceptions import ValidationError as APIValidationError
            raise APIValidationError("Only draft items can be edited in place.")
        try:
            workflow._owner(serializer.instance, self.request.user)
        except PermissionDenied:
            from rest_framework.exceptions import PermissionDenied as APIPermissionDenied
            raise APIPermissionDenied("Mechanics may only edit their own content.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status in (Status.APPROVED, Status.PUBLISHED):
            from rest_framework.exceptions import ValidationError as APIValidationError
            raise APIValidationError("Approved content cannot be deleted.")
        if (isinstance(instance, (SelfCheck, RepairCost)) and
                instance.cause.status in (Status.APPROVED, Status.PUBLISHED)):
            from rest_framework.exceptions import ValidationError as APIValidationError
            raise APIValidationError(
                "Self-checks and costs on approved causes belong in a cause revision.")

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status in (Status.APPROVED, Status.PUBLISHED):
            partial = kwargs.pop("partial", False)
            serializer = self.get_serializer(instance, data=request.data,
                                             partial=partial)
            serializer.is_valid(raise_exception=True)
            payload = {}
            for key, value in serializer.validated_data.items():
                if hasattr(value, "pk"):
                    payload[f"{key}_id"] = value.pk
                elif key == "car_models":
                    payload[key] = [obj.pk if hasattr(obj, "pk") else obj
                                    for obj in value]
                else:
                    payload[key] = value
            if isinstance(instance, (Cause, Question)):
                from .services.workflow import _snapshot
                current = _snapshot(instance)
                current.update(payload)
                allowed = {field.attname for field in instance._meta.concrete_fields}
                allowed -= {"id", "status", "is_dummy", "version", "created_by_id",
                            "approved_by_id", "created_at", "updated_at"}
                payload = {key: _revision_value(value) for key, value in current.items()
                           if key in allowed or key in
                           {"links", "self_checks", "costs", "car_models", "options"}}
            revision = workflow.create_revision(instance, request.user, payload)
            return Response({"id": revision.pk, "object_id": revision.object_id,
                             "base_version": revision.base_version,
                             "payload": revision.payload,
                             "status": revision.status}, status=http_status.HTTP_202_ACCEPTED)
        return super().update(request, *args, **kwargs)

    def _move(self, request, name):
        obj = self.get_object()
        try:
            result = getattr(workflow, name)(obj, request.user,
                    **({"comment": request.data.get("comment", "")} if name in
                       {"approve", "return_for_changes", "reject"} else {}))
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_403_FORBIDDEN)
        except (workflow.WorkflowError, ValidationError) as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self._move(request, "submit")

    @action(detail=True, methods=["post"])
    def start_review(self, request, pk=None):
        return self._move(request, "start_review")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._move(request, "approve")

    @action(detail=True, methods=["post"])
    def return_for_changes(self, request, pk=None):
        return self._move(request, "return_for_changes")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._move(request, "reject")

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        return self._move(request, "publish")


class SymptomCategoryViewSet(KnowledgeViewSet):
    queryset = SymptomCategory.objects.all().order_by("id")
    serializer_class = SymptomCategorySerializer
    search_fields = ["name_en", "name_roman", "name_ur"]


class SymptomViewSet(GovernedViewSet):
    queryset = Symptom.objects.select_related("category").order_by("id")
    serializer_class = SymptomSerializer
    search_fields = ["text_en", "text_roman"]
    filter_params = {"category": "category_id",
                     "safety_critical": "is_safety_critical"}


class CauseViewSet(GovernedViewSet):
    queryset = Cause.objects.prefetch_related("links").order_by("id")
    serializer_class = CauseSerializer
    search_fields = ["name", "system", "description"]
    filter_params = {"system": "system", "severity": "severity",
                     "car_model": "car_models"}


class QuestionViewSet(GovernedViewSet):
    queryset = Question.objects.prefetch_related("options").order_by("id")
    serializer_class = QuestionSerializer
    search_fields = ["text_en", "text_roman"]
    filter_params = {"symptom": "symptom_id",
                     "category": "symptom__category_id"}


class CauseSymptomLinkViewSet(KnowledgeViewSet):
    queryset = CauseSymptomLink.objects.select_related("cause", "symptom")
    serializer_class = CauseSymptomLinkSerializer
    public_filter = {}
    filter_params = {"cause": "cause_id", "symptom": "symptom_id"}

    def get_permissions(self):
        return [IsReviewerOrAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_staff_role(self.request.user):
            return queryset
        return queryset.filter(
            cause__in=Cause.objects.visible(),
            symptom__in=Symptom.objects.visible(),
        )

    def _check_cause_revision(self, cause):
        if cause.status in (Status.APPROVED, Status.PUBLISHED):
            from rest_framework.exceptions import ValidationError as APIValidationError
            raise APIValidationError(
                "Links on approved content must be changed in a cause revision.")

    def perform_create(self, serializer):
        self._check_cause_revision(serializer.validated_data["cause"])
        serializer.save()

    def perform_update(self, serializer):
        self._check_cause_revision(serializer.instance.cause)
        self._check_cause_revision(serializer.validated_data.get(
            "cause", serializer.instance.cause))
        serializer.save()

    def perform_destroy(self, instance):
        self._check_cause_revision(instance.cause)
        instance.delete()


class AnswerOptionViewSet(KnowledgeViewSet):
    queryset = AnswerOption.objects.all().order_by("id")
    serializer_class = AnswerOptionSerializer
    public_filter = {"question__status": Status.PUBLISHED}
    filter_params = {"question": "question_id"}

    def get_permissions(self):
        # implies_symptom is scoring logic: staff only (users get options
        # through the question endpoints instead).
        return [IsReviewerOrAdmin()]

    @staticmethod
    def _check_question_revision(question):
        if question.status in (Status.APPROVED, Status.PUBLISHED):
            from rest_framework.exceptions import ValidationError as APIValidationError
            raise APIValidationError(
                "Options on approved questions must be changed in a question revision.")

    def perform_create(self, serializer):
        self._check_question_revision(serializer.validated_data["question"])
        serializer.save()

    def perform_update(self, serializer):
        self._check_question_revision(serializer.instance.question)
        self._check_question_revision(serializer.validated_data.get(
            "question", serializer.instance.question))
        serializer.save()

    def perform_destroy(self, instance):
        self._check_question_revision(instance.question)
        instance.delete()


class SelfCheckViewSet(GovernedViewSet):
    queryset = SelfCheck.objects.select_related("cause").order_by("id")
    serializer_class = SelfCheckSerializer
    filter_params = {"cause": "cause_id"}


class RepairCostViewSet(GovernedViewSet):
    queryset = RepairCost.objects.select_related("cause").order_by("id")
    serializer_class = RepairCostSerializer
    filter_params = {"cause": "cause_id", "city": "city__iexact"}


class WarningLightViewSet(KnowledgeViewSet):
    queryset = WarningLight.objects.all().order_by("name")
    serializer_class = WarningLightSerializer
    search_fields = ["name", "meaning"]
    filter_params = {"severity": "severity"}

    def get_queryset(self):
        queryset = super().get_queryset()
        if not is_staff_role(self.request.user) and not settings.ALLOW_DRAFT_CONTENT:
            queryset = queryset.filter(is_dummy=False)
        return queryset


class ObdCodeViewSet(KnowledgeViewSet):
    queryset = ObdCode.objects.all().order_by("code")
    serializer_class = ObdCodeSerializer
    search_fields = ["code", "description"]
    filter_params = {"system": "system"}


class PublicCategoriesView(DraftContentResponseMixin, generics.ListAPIView):
    queryset = SymptomCategory.objects.all().order_by("name_en")
    serializer_class = SymptomCategorySerializer
    permission_classes = [AllowAny]
    throttle_classes = [throttling.AnonRateThrottle, throttling.UserRateThrottle]

    @extend_schema(responses=SymptomCategorySerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PublicWarningLightsView(DraftContentResponseMixin, generics.ListAPIView):
    serializer_class = WarningLightSerializer
    permission_classes = [AllowAny]
    throttle_classes = [throttling.AnonRateThrottle, throttling.UserRateThrottle]

    @extend_schema(responses=WarningLightSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = WarningLight.objects.all().order_by("name")
        from django.conf import settings
        if not settings.ALLOW_DRAFT_CONTENT:
            queryset = queryset.filter(is_dummy=False)
        return queryset


class PublicObdCodeView(DraftContentResponseMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [throttling.AnonRateThrottle, throttling.UserRateThrottle]

    @extend_schema(responses=PublicObdCodeSerializer)
    def get(self, request, code):
        from django.http import Http404
        try:
            obj = ObdCode.objects.get(code__iexact=code.strip())
        except ObdCode.DoesNotExist as exc:
            raise Http404("OBD code not found") from exc
        data = PublicObdCodeSerializer(obj).data
        return Response(data)


class ContentReviewViewSet(DraftContentResponseMixin, ParamFilterMixin,
                           viewsets.ReadOnlyModelViewSet):
    queryset = ContentReview.objects.select_related("content_type")
    serializer_class = ContentReviewSerializer
    permission_classes = [IsReviewerOrAdmin]
    filter_params = {"model": "content_type__model", "object_id": "object_id",
                     "status": "status"}


class ImportFlowView(APIView):
    """POST a diagnostic-flow JSON body. Admin only."""
    permission_classes = [IsAdminRole]

    @extend_schema(request=OpenApiTypes.OBJECT, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        try:
            counts = import_flow(request.data, user=request.user)
        except ImportErrorInFile as e:
            return Response({"detail": str(e)}, status=400)
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            return Response({"detail": f"Bad file structure: {e!r}"},
                            status=400)
        return Response({"imported": counts}, status=201)
