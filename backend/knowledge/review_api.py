"""Reviewer queue and audited workflow endpoints."""
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsReviewer
from .models import (Cause, ContentRevision, ContentReview, Question, RepairCost,
                     SelfCheck, Status, Symptom)
from .services import workflow
from .services.launch_gate import run_launch_checks

ITEM_TYPES = {"symptom": Symptom, "cause": Cause, "question": Question,
              "self-check": SelfCheck, "repair-cost": RepairCost}


class ReviewActionSerializer(serializers.Serializer):
    revision_id = serializers.IntegerField(required=False, min_value=1)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    conflict_resolution = serializers.ChoiceField(required=False, choices=[
        "keep_both", "ask_third", "cautious_option"])


class ReviewQueueEntrySerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.IntegerField()
    status = serializers.CharField()
    revision_id = serializers.IntegerField(allow_null=True)
    author = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    safety_critical = serializers.BooleanField()
    label = serializers.CharField(allow_blank=True)


class ReviewItemDetailSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.IntegerField()
    status = serializers.CharField()
    safety_critical = serializers.BooleanField()
    current = serializers.JSONField()
    proposed = serializers.JSONField(allow_null=True)
    revision_id = serializers.IntegerField(allow_null=True)
    diff = serializers.ListField(child=serializers.JSONField())
    conflicts = serializers.ListField(child=serializers.JSONField())
    history = serializers.ListField(child=serializers.JSONField())


def _snapshot(item):
    return workflow._snapshot(item)


def _revision_payload(revision):
    return revision.payload if revision else None


def _link_keys(payload):
    return {row.get("symptom") for row in payload.get("links", [])
            if isinstance(row, dict) and row.get("symptom") is not None}


def _conflicts(revision):
    qs = ContentRevision.objects.filter(
        content_type=revision.content_type, object_id=revision.object_id,
        status__in=[ContentRevision.RevisionStatus.SUBMITTED,
                    ContentRevision.RevisionStatus.UNDER_REVIEW],
    ).exclude(pk=revision.pk).select_related("author")
    result = []
    for other in qs:
        shared = _link_keys(revision.payload) & _link_keys(other.payload)
        # Same live cause means opinions can still conflict through parent fields;
        # report concrete overlapping link symptom ids when nested links overlap.
        result.append({"revision_id": other.pk, "author": getattr(other.author, "username", ""),
                       "payload": other.payload, "shared_link_symptom_ids": sorted(shared)})
    return result


def _field_diff(current, proposed):
    if proposed is None:
        return []
    keys = sorted(set(current) | set(proposed))
    return [{"field": key, "current": current.get(key), "proposed": proposed.get(key)}
            for key in keys if current.get(key) != proposed.get(key)]


def _flow_filter(model, queryset, flow):
    if not flow:
        return queryset
    paths = {Symptom: "category_id", Cause: "links__symptom__category_id",
             Question: "symptom__category_id", SelfCheck: "cause__links__symptom__category_id",
             RepairCost: "cause__links__symptom__category_id"}
    path = paths.get(model)
    return queryset.filter(**{path: flow}).distinct() if path else queryset


class ReviewQueueView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    @extend_schema(responses=ReviewQueueEntrySerializer(many=True), parameters=[OpenApiParameter("type", OpenApiTypes.STR),
                               OpenApiParameter("flow", OpenApiTypes.INT),
                               OpenApiParameter("mechanic", OpenApiTypes.INT)])
    def get(self, request):
        item_type = request.query_params.get("type")
        flow = request.query_params.get("flow")
        mechanic = request.query_params.get("mechanic")
        queue = []
        for slug, model in ITEM_TYPES.items():
            if item_type and item_type != slug:
                continue
            qs = model.objects.filter(status__in=[Status.SUBMITTED, Status.UNDER_REVIEW])
            qs = _flow_filter(model, qs, flow)
            if mechanic:
                qs = qs.filter(created_by_id=mechanic)
            for item in qs.select_related("created_by"):
                safety = isinstance(item, Symptom) and item.is_safety_critical
                if isinstance(item, Question):
                    safety = item.symptom.is_safety_critical
                if isinstance(item, (SelfCheck, RepairCost)):
                    safety = item.cause.links.filter(symptom__is_safety_critical=True).exists()
                queue.append({"type": slug, "id": item.pk, "status": item.status,
                              "revision_id": None, "author": getattr(item.created_by, "username", ""),
                              "created_at": item.created_at, "safety_critical": safety,
                              "label": getattr(item, "name", getattr(item, "text_en", ""))})
        for revision in ContentRevision.objects.filter(status__in=[
                ContentRevision.RevisionStatus.SUBMITTED,
                ContentRevision.RevisionStatus.UNDER_REVIEW]).select_related("content_type", "author"):
            model = revision.content_type.model_class()
            slug = next((key for key, value in ITEM_TYPES.items() if value is model), None)
            if not slug or (item_type and item_type != slug):
                continue
            if mechanic and revision.author_id != int(mechanic):
                continue
            live = revision.content_object
            if flow and not _flow_filter(model, model.objects.filter(pk=live.pk), flow).exists():
                continue
            safety = isinstance(live, Symptom) and live.is_safety_critical
            if isinstance(live, Question):
                safety = live.symptom.is_safety_critical
            if isinstance(live, (SelfCheck, RepairCost)):
                safety = live.cause.links.filter(symptom__is_safety_critical=True).exists()
            queue.append({"type": slug, "id": live.pk, "status": revision.status,
                          "revision_id": revision.pk, "author": getattr(revision.author, "username", ""),
                          "created_at": revision.created_at, "safety_critical": safety,
                          "label": getattr(live, "name", getattr(live, "text_en", ""))})
        queue.sort(key=lambda row: (not row["safety_critical"], -row["created_at"].timestamp()))
        return Response(queue)


class LaunchGateView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(run_launch_checks())


class ReviewItemView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    @extend_schema(responses=ReviewItemDetailSerializer, parameters=[OpenApiParameter("revision_id", OpenApiTypes.INT)])
    def get(self, request, item_type, item_id):
        model = ITEM_TYPES.get(item_type)
        if not model:
            return Response({"detail": "Unknown review item type."}, status=404)
        try:
            item = model.objects.get(pk=item_id)
        except model.DoesNotExist:
            return Response({"detail": "Review item not found."}, status=404)
        current = _snapshot(item)
        revision_id = request.query_params.get("revision_id")
        revisions = ContentRevision.objects.filter(content_type=ContentType.objects.get_for_model(model),
                                                    object_id=item.pk)
        selected = revisions.filter(pk=revision_id).first() if revision_id else revisions.filter(
            status__in=["submitted", "under_review"]).first()
        proposed = _revision_payload(selected) if selected else current
        conflicts = _conflicts(selected) if selected else []
        history = [{"status": event.status, "actor": getattr(event.reviewed_by or event.submitted_by,
                                                               "username", "Unknown"),
                    "comment": event.comment, "version": event.version,
                    "created_at": event.created_at, "snapshot": event.snapshot}
                   for event in ContentReview.objects.filter(content_type=ContentType.objects.get_for_model(model),
                                                              object_id=item.pk).select_related("reviewed_by", "submitted_by")]
        safety = isinstance(item, Symptom) and item.is_safety_critical
        if isinstance(item, Question):
            safety = item.symptom.is_safety_critical
        if isinstance(item, Cause):
            safety = item.links.filter(symptom__is_safety_critical=True).exists()
        if isinstance(item, (SelfCheck, RepairCost)):
            safety = item.cause.links.filter(symptom__is_safety_critical=True).exists()
        return Response({"type": item_type, "id": item.pk, "status": selected.status if selected else item.status,
                         "safety_critical": safety, "current": current, "proposed": proposed,
                         "revision_id": selected.pk if selected else None,
                         "diff": _field_diff(current, proposed), "conflicts": conflicts,
                         "history": history})


class ReviewActionView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]
    action_name = None
    serializer_class = ReviewActionSerializer

    @extend_schema(request=ReviewActionSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, item_type, item_id):
        model = ITEM_TYPES.get(item_type)
        if not model:
            return Response({"detail": "Unknown review item type."}, status=404)
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            item = model.objects.get(pk=item_id)
            target = (ContentRevision.objects.get(pk=data["revision_id"],
                    content_type=ContentType.objects.get_for_model(model), object_id=item_id)
                      if data.get("revision_id") else item)
            action = self.action_name
            if action == "start":
                workflow.start_review(target, request.user)
            elif action == "approve":
                conflicts = _conflicts(target) if isinstance(target, ContentRevision) else []
                comment = data.get("comment", "")
                if conflicts and (not comment.strip() or not data.get("conflict_resolution")):
                    return Response({"detail": "Resolve the conflicting opinions and add a resolution comment.",
                                     "conflicts": conflicts}, status=400)
                if conflicts:
                    comment = f"Conflict resolution ({data['conflict_resolution']}): {comment.strip()}"
                workflow.approve(target, request.user, comment=comment)
            elif action == "return":
                workflow.return_for_changes(target, request.user, data.get("comment", ""))
            elif action == "reject":
                workflow.reject(target, request.user, data.get("comment", ""))
            else:
                workflow.publish(target, request.user)
        except model.DoesNotExist:
            return Response({"detail": "Review item not found."}, status=404)
        except ContentRevision.DoesNotExist:
            return Response({"detail": "Revision not found."}, status=404)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=403)
        except (workflow.WorkflowError, ValidationError) as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


def action_view(action):
    return type(f"{action.title()}ReviewActionView", (ReviewActionView,), {"action_name": action}).as_view()
