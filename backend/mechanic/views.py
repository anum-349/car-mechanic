from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from accounts.models import MechanicProfile
from accounts.permissions import IsMechanic, IsReviewer
from garage.models import CarModel
from knowledge.models import (
    AnswerOption, Cause, CauseSymptomLink, Question, RepairCost,
    SelfCheck, Status, Symptom,
)
from knowledge.services import workflow

from . import services
from .serializers import (
    FlowInputSerializer, ITEM_SERIALIZERS, MechanicRegistrationResponseSerializer,
    MechanicRegistrationSerializer, MechanicSelfProfileSerializer,
    AiDraftRejectSerializer, SimulationInputSerializer, item_serializer,
)


class MechanicRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=MechanicRegistrationSerializer,
                   responses={201: MechanicRegistrationResponseSerializer})
    def post(self, request):
        serializer = MechanicRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            result = serializer.save()
        return Response(MechanicRegistrationResponseSerializer(result).data,
                        status=status.HTTP_201_CREATED)


class MechanicSelfProfileView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    @extend_schema(responses=MechanicSelfProfileSerializer)
    def get(self, request):
        profile = get_object_or_404(MechanicProfile, user=request.user)
        return Response(MechanicSelfProfileSerializer(profile).data)

    @extend_schema(request=MechanicSelfProfileSerializer,
                   responses=MechanicSelfProfileSerializer)
    def patch(self, request):
        blocked = {"is_verified", "honesty_score", "user"}.intersection(request.data)
        if blocked:
            raise ValidationError({key: "This profile field is read-only."
                                   for key in sorted(blocked)})
        profile = get_object_or_404(MechanicProfile, user=request.user)
        serializer = MechanicSelfProfileSerializer(profile, data=request.data,
                                                    partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MechanicFlowsView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    @extend_schema(operation_id="mechanic_flow_list",
                   responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response([services.flow_data(category, request.user)
                         for category in services.flow_queryset(request.user)])

    @extend_schema(operation_id="mechanic_flow_create",
                   request=OpenApiTypes.OBJECT,
                   responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = FlowInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.save_flow(serializer.validated_data, request.user)
        return Response(services.flow_data(category, request.user),
                        status=status.HTTP_201_CREATED)


class MechanicFlowDetailView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def _category(self, request, pk):
        return get_object_or_404(services.flow_queryset(request.user), pk=pk)

    @extend_schema(operation_id="mechanic_flow_retrieve",
                   responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        return Response(services.flow_data(self._category(request, pk), request.user))

    @extend_schema(operation_id="mechanic_flow_replace",
                   request=OpenApiTypes.OBJECT,
                   responses={200: OpenApiTypes.OBJECT})
    def put(self, request, pk):
        return self._write(request, pk)

    @extend_schema(operation_id="mechanic_flow_update",
                   request=OpenApiTypes.OBJECT,
                   responses={200: OpenApiTypes.OBJECT})
    def patch(self, request, pk):
        return self._write(request, pk)

    def _write(self, request, pk):
        category = self._category(request, pk)
        serializer = FlowInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.save_flow(serializer.validated_data, request.user,
                                      category=category)
        return Response(services.flow_data(category, request.user))

    @extend_schema(operation_id="mechanic_flow_delete", responses={204: None})
    def delete(self, request, pk):
        category = self._category(request, pk)
        services.delete_flow(category, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MechanicDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    @extend_schema(responses={200: dict})
    def get(self, request):
        user = request.user
        models = [Symptom, Cause, SelfCheck, RepairCost, Question]
        owned = {model: model.objects.filter(created_by=user) for model in models}
        counts = {state: sum(query.filter(status=state).count()
                             for query in owned.values()) for state, _ in Status.choices}
        items = []
        for model, queryset in owned.items():
            items.extend([{"type": model._meta.model_name, "id": item.pk,
                           "label": str(item), "status": item.status}
                          for item in queryset.order_by("-updated_at")])
        flows = []
        for category in services.flow_queryset(user):
            flows.append({"id": category.pk, "name": category.name_en,
                          **services.flow_progress(category, user)})
        return Response({"counts_by_status": counts, "items": items,
                         "flows": flows})


def item_model(item_type):
    if item_type not in ITEM_SERIALIZERS:
        raise ValidationError({"type": "Unknown mechanic content type."})
    return ITEM_SERIALIZERS[item_type].Meta.model


def item_queryset(item_type, user):
    model = item_model(item_type)
    if model in services.GOVERNED_TYPES.values():
        return services.editable_items(model.objects.all(), user)
    if model is CauseSymptomLink:
        return CauseSymptomLink.objects.filter(
            cause__in=services.editable_items(Cause.objects.all(), user))
    if model is AnswerOption:
        return AnswerOption.objects.filter(
            question__in=services.editable_items(Question.objects.all(), user))
    return model.objects.none()


def _reject_control_fields(data):
    locked = {"is_dummy", "version", "created_by", "approved_by", "weight"}
    present = locked.intersection(data)
    if present:
        raise ValidationError({key: "This field is managed by the workflow."
                               for key in sorted(present)})
    if "status" in data and data["status"] not in {Status.DRAFT, Status.SUBMITTED}:
        raise ValidationError({"status": "Mechanics may only write draft or submitted content."})


def _check_references(item_type, values, user):
    targets = []
    if item_type == "links":
        targets = [values.get("cause"), values.get("symptom")]
    elif item_type in {"self-checks", "repair-costs"}:
        targets = [values.get("cause")]
    elif item_type == "questions":
        targets = [values.get("symptom")]
    elif item_type == "options":
        targets = [values.get("question"), values.get("implies_symptom")]
    for target in targets:
        if target is None:
            continue
        if isinstance(target, CauseSymptomLink):
            continue
        if isinstance(target, Cause):
            services.require_editable(target, user)
        elif isinstance(target, Symptom):
            services.require_editable(target, user)
        elif isinstance(target, Question):
            services.require_editable(target, user)
    if item_type == "questions":
        for option in values.get("options", []):
            symptom = option.get("implies_symptom")
            if symptom is not None:
                services.require_editable(symptom, user)


def _validate_cost(serializer):
    if not isinstance(serializer.instance, RepairCost) and serializer.Meta.model is not RepairCost:
        return
    attrs = serializer.validated_data
    for low, high in (("parts_min", "parts_max"), ("labour_min", "labour_max")):
        low_value = attrs.get(low, getattr(serializer.instance, low, 0)
                              if serializer.instance else 0)
        high_value = attrs.get(high, getattr(serializer.instance, high, 0)
                               if serializer.instance else 0)
        if low_value > high_value:
            raise ValidationError({low: f"Must be less than or equal to {high}."})


class MechanicItemCollectionView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    @extend_schema(operation_id="mechanic_item_list",
                   responses={200: OpenApiTypes.OBJECT})
    def get(self, request, item_type):
        model = item_model(item_type)
        queryset = item_queryset(item_type, request.user)
        serializer = item_serializer(item_type, queryset, many=True)
        return Response(serializer.data)

    @extend_schema(operation_id="mechanic_item_create",
                   request=OpenApiTypes.OBJECT,
                   responses={201: OpenApiTypes.OBJECT})
    def post(self, request, item_type):
        _reject_control_fields(request.data)
        if (request.data.get("status") == Status.SUBMITTED and
                item_model(item_type) not in services.GOVERNED_TYPES.values()):
            raise ValidationError({"status": "Only governed items can be submitted."})
        serializer = item_serializer(item_type, data=request.data)
        serializer.is_valid(raise_exception=True)
        _check_references(item_type, serializer.validated_data, request.user)
        _validate_cost(serializer)
        with transaction.atomic():
            if serializer.Meta.model in services.GOVERNED_TYPES.values():
                item = serializer.save(created_by=request.user, status=Status.DRAFT,
                                       is_dummy=False)
            else:
                item = serializer.save()
            if request.data.get("status") == Status.SUBMITTED:
                try:
                    workflow.submit(item, request.user)
                except DjangoPermissionDenied as exc:
                    raise PermissionDenied(str(exc)) from exc
        return Response(item_serializer(item_type, item).data,
                        status=status.HTTP_201_CREATED)


class MechanicItemDetailView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]

    def _item(self, request, item_type, pk):
        return get_object_or_404(item_queryset(item_type, request.user), pk=pk)

    @extend_schema(operation_id="mechanic_item_retrieve",
                   responses={200: OpenApiTypes.OBJECT})
    def get(self, request, item_type, pk):
        return Response(item_serializer(item_type, self._item(request, item_type, pk)).data)

    @extend_schema(operation_id="mechanic_item_replace",
                   request=OpenApiTypes.OBJECT,
                   responses={200: OpenApiTypes.OBJECT})
    def put(self, request, item_type, pk):
        return self._write(request, item_type, pk, partial=False)

    @extend_schema(operation_id="mechanic_item_update",
                   request=OpenApiTypes.OBJECT,
                   responses={200: OpenApiTypes.OBJECT})
    def patch(self, request, item_type, pk):
        return self._write(request, item_type, pk, partial=True)

    def _write(self, request, item_type, pk, partial):
        _reject_control_fields(request.data)
        if (request.data.get("status") == Status.SUBMITTED and
                item_model(item_type) not in services.GOVERNED_TYPES.values()):
            raise ValidationError({"status": "Only governed items can be submitted."})
        item = self._item(request, item_type, pk)
        if isinstance(item, (CauseSymptomLink, AnswerOption)):
            parent = item.cause if isinstance(item, CauseSymptomLink) else item.question
            services.require_editable(parent, request.user)
        else:
            services.require_editable(item, request.user)
        serializer = item_serializer(item_type, item, data=request.data,
                                     partial=partial)
        serializer.is_valid(raise_exception=True)
        _check_references(item_type, serializer.validated_data, request.user)
        _validate_cost(serializer)
        with transaction.atomic():
            saved = serializer.save()
            if request.data.get("status") == Status.SUBMITTED:
                try:
                    workflow.submit(saved, request.user)
                except DjangoPermissionDenied as exc:
                    raise PermissionDenied(str(exc)) from exc
        return Response(item_serializer(item_type, saved).data)

    @extend_schema(operation_id="mechanic_item_delete", responses={204: None})
    def delete(self, request, item_type, pk):
        item = self._item(request, item_type, pk)
        if isinstance(item, (CauseSymptomLink, AnswerOption)):
            parent = item.cause if isinstance(item, CauseSymptomLink) else item.question
            services.require_editable(parent, request.user)
        else:
            services.require_editable(item, request.user)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MechanicItemClaimView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]
    serializer_class = MechanicSelfProfileSerializer

    @extend_schema(operation_id="mechanic_item_claim",
                   responses={200: OpenApiTypes.OBJECT})
    def post(self, request, item_type, pk):
        model = item_model(item_type)
        if model not in services.GOVERNED_TYPES.values():
            raise ValidationError({"type": "Only governed draft items can be claimed."})
        item = get_object_or_404(
            model, pk=pk, created_by__isnull=True,
            status__in=[Status.AI_DRAFT, Status.DRAFT])
        result = workflow.claim(item, request.user)
        return Response(item_serializer(item_type, result).data)


class MechanicItemSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]
    serializer_class = MechanicSelfProfileSerializer

    @extend_schema(operation_id="mechanic_item_submit",
                   responses={200: OpenApiTypes.OBJECT})
    def post(self, request, item_type, pk):
        model = item_model(item_type)
        if model not in services.GOVERNED_TYPES.values():
            raise ValidationError({"type": "This item type cannot be submitted."})
        item = get_object_or_404(model, created_by=request.user, pk=pk)
        try:
            result = workflow.submit(item, request.user)
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(item_serializer(item_type, result).data)


class MechanicForbiddenReviewActionView(APIView):
    permission_classes = [IsAuthenticated, IsMechanic]
    serializer_class = MechanicSelfProfileSerializer

    @extend_schema(operation_id="mechanic_item_forbidden_review_action",
                   responses={403: OpenApiTypes.OBJECT})
    def post(self, request, item_type, pk, action):
        return Response({"detail": "Only reviewers and admins may approve or publish content."},
                        status=status.HTTP_403_FORBIDDEN)


IsMechanicOrReviewer = IsMechanic | IsReviewer


class MechanicSimulatorView(APIView):
    permission_classes = [IsAuthenticated, IsMechanicOrReviewer]

    @extend_schema(operation_id="mechanic_simulate_flow",
                   request=SimulationInputSerializer,
                   responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = SimulationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        from knowledge.simulator import simulate
        result = simulate(car_model=values["car_model"],
                          category=values["category"], user=request.user,
                          answers=values["answers"],
                          include_drafts=values["include_drafts"])
        return Response(result)


def _specialty_system(profile):
    value = (profile.specialization if profile else "").strip().lower()
    if not value:
        return ""
    aliases = (("electric", "electrical"), ("cool", "cooling"),
               ("fuel", "fuel"), ("brake", "brakes"),
               ("engine", "engine"), ("transmission", "transmission"))
    return next((system for token, system in aliases if token in value), value)


class MechanicAiDraftListView(APIView):
    permission_classes = [IsAuthenticated, IsMechanicOrReviewer]

    @extend_schema(operation_id="mechanic_ai_drafts_list",
                   responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        specialty = _specialty_system(getattr(request.user, "mechanic_profile", None))
        model_id = request.query_params.get("car_model_id")
        if model_id and (not str(model_id).isdigit() or
                         not CarModel.objects.filter(pk=model_id).exists()):
            raise ValidationError({"car_model_id": "Choose a valid car model."})
        eligible_causes = Cause.objects.filter(status=Status.AI_DRAFT,
                                               created_by__isnull=True)
        if specialty:
            eligible_causes = eligible_causes.filter(system__icontains=specialty)
        if model_id:
            eligible_causes = eligible_causes.filter(
                Q(car_models__pk=model_id) | Q(car_models__isnull=True)).distinct()
        cause_ids = eligible_causes.values_list("pk", flat=True)
        symptom_ids = Symptom.objects.filter(links__cause_id__in=cause_ids).values("pk")
        queryset_map = {
            "symptoms": Symptom.objects.filter(status=Status.AI_DRAFT,
                                                created_by__isnull=True),
            "causes": eligible_causes,
            "self-checks": SelfCheck.objects.filter(status=Status.AI_DRAFT,
                                                     created_by__isnull=True,
                                                     cause_id__in=cause_ids),
            "repair-costs": RepairCost.objects.filter(status=Status.AI_DRAFT,
                                                       created_by__isnull=True,
                                                       cause_id__in=cause_ids),
            "questions": Question.objects.filter(status=Status.AI_DRAFT,
                                                  created_by__isnull=True,
                                                  symptom_id__in=symptom_ids),
        }
        if specialty:
            queryset_map["symptoms"] = queryset_map["symptoms"].filter(
                links__cause_id__in=cause_ids).distinct()
        if model_id:
            queryset_map["symptoms"] = queryset_map["symptoms"].filter(
                links__cause__in=eligible_causes).distinct()
            queryset_map["questions"] = queryset_map["questions"].filter(
                symptom__links__cause__in=eligible_causes).distinct()
        results = []
        for item_type, queryset in queryset_map.items():
            serializer_class = ITEM_SERIALIZERS[item_type]
            for item in queryset.order_by("pk"):
                results.append({"type": item_type, "id": item.pk,
                                "status": item.status, "label": str(item),
                                "data": serializer_class(item).data})
        return Response(results)


class MechanicAiDraftActionView(APIView):
    permission_classes = [IsAuthenticated, IsMechanicOrReviewer]
    serializer_class = AiDraftRejectSerializer

    def _mechanic(self, request):
        if request.user.role != "mechanic":
            raise PermissionDenied("Only mechanics can take ownership of AI drafts.")

    def _draft(self, item_type, pk):
        model = item_model(item_type)
        if model not in services.GOVERNED_TYPES.values():
            raise ValidationError({"type": "This item type cannot be reviewed here."})
        return get_object_or_404(model, pk=pk, status=Status.AI_DRAFT,
                                 created_by__isnull=True)

    @extend_schema(operation_id="mechanic_ai_draft_approve_as_is",
                   responses={200: OpenApiTypes.OBJECT})
    def post(self, request, item_type, pk, action):
        self._mechanic(request)
        item = self._draft(item_type, pk)
        if action == "approve-as-is":
            try:
                with transaction.atomic():
                    workflow.claim(item, request.user)
                    result = workflow.submit(item, request.user)
            except DjangoPermissionDenied as exc:
                raise PermissionDenied(str(exc)) from exc
            return Response(item_serializer(item_type, result).data)
        if action == "reject":
            serializer = AiDraftRejectSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                result = workflow.reject_ai_draft(item, request.user,
                                                  serializer.validated_data["reason"])
            except DjangoPermissionDenied as exc:
                raise PermissionDenied(str(exc)) from exc
            except workflow.WorkflowError as exc:
                raise ValidationError(str(exc)) from exc
            return Response(item_serializer(item_type, result).data)
        raise ValidationError({"action": "Use approve-as-is or reject."})
