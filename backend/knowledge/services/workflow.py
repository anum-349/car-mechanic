"""Transactional workflow for governed knowledge and its revisions."""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone
import json

from accounts.models import MechanicProfile
from knowledge.models import (
    AnswerOption, Cause, CauseSymptomLink, ContentRevision, ContentReview,
    Question, RepairCost, SelfCheck, Status,
)


class WorkflowError(Exception):
    """A requested content workflow transition is not valid."""


def _role(user):
    return getattr(user, "role", "")


def _reviewer(user):
    return bool(user and user.is_authenticated and (
        _role(user) in {"reviewer", "admin"} or user.is_superuser
    ))


def _require_reviewer(user):
    if not _reviewer(user):
        raise PermissionDenied("Only reviewers and admins may review content.")


def _owner(item, user):
    if _role(user) == "mechanic" and item.created_by_id != user.pk:
        raise PermissionDenied("Mechanics may only change their own content.")
    if _role(user) not in {"mechanic", "reviewer", "admin"} and not user.is_superuser:
        raise PermissionDenied("Only mechanics, reviewers, and admins may change content.")


def _snapshot(item):
    data = {field.attname: getattr(item, field.attname)
            for field in item._meta.concrete_fields}
    if isinstance(item, Cause):
        data.update(
            car_models=list(item.car_models.values_list("pk", flat=True)),
            links=[{"symptom": x.symptom_id, "strength": x.strength,
                    "car_model": x.car_model_id}
                   for x in item.links.order_by("pk")],
            self_checks=[{k: getattr(x, k) for k in
                          ("id", "steps", "tools_needed", "difficulty", "status",
                           "is_dummy", "version")}
                         for x in item.self_checks.order_by("pk")],
            costs=[{k: getattr(x, k) for k in
                    ("id", "city", "parts_min", "parts_max", "labour_min",
                     "labour_max", "last_verified", "source", "status",
                     "is_dummy", "version")}
                   for x in item.costs.order_by("pk")],
        )
    if isinstance(item, Question):
        data["options"] = [{"label": option.label,
                             "label_roman": option.label_roman,
                             "is_unsure": option.is_unsure,
                             "implies_symptom_id": option.implies_symptom_id}
                            for option in item.options.order_by("pk")]
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def _log(item, decision, actor, *, submitted_by=None, comment="", snapshot=None,
         version=None, reviewed=True):
    return ContentReview.objects.create(
        content_type=ContentType.objects.get_for_model(item), object_id=item.pk,
        version=version if version is not None else item.version,
        status=decision, submitted_by=submitted_by,
        reviewed_by=actor if reviewed else None, comment=comment,
        snapshot=snapshot if snapshot is not None else _snapshot(item),
        reviewed_at=timezone.now() if reviewed else None,
    )


def _is_revision(value):
    return isinstance(value, ContentRevision)


def _live(value):
    return value.content_object if _is_revision(value) else value


@transaction.atomic
def submit(item, user):
    """Submit a draft item or pending revision for review."""
    if _is_revision(item):
        revision = item
        live = _live(revision)
        _owner(live, user)
        _require_verified_mechanic(user)
        if revision.author_id != user.pk and _role(user) == "mechanic":
            raise PermissionDenied("Mechanics may only submit their own revisions.")
        if revision.status not in {ContentRevision.RevisionStatus.PENDING,
                                   ContentRevision.RevisionStatus.RETURNED}:
            raise WorkflowError("Only pending or returned revisions can be submitted.")
        revision.status = ContentRevision.RevisionStatus.SUBMITTED
        revision.save(update_fields=["status"])
        _log(live, ContentReview.Decision.SUBMITTED, user,
             submitted_by=revision.author, snapshot={"revision_id": revision.pk,
             "base_version": revision.base_version, "payload": revision.payload},
             version=revision.base_version, reviewed=False)
        return revision
    _owner(item, user)
    _require_verified_mechanic(user)
    if item.status not in {Status.DRAFT, Status.AI_DRAFT}:
        raise WorkflowError("Only draft content can be submitted.")
    item.status = Status.SUBMITTED
    item.save(update_fields=["status", "updated_at"])
    _log(item, ContentReview.Decision.SUBMITTED, user,
         submitted_by=item.created_by or user, reviewed=False)
    return item


def _require_verified_mechanic(user):
    if _role(user) == "mechanic" and not MechanicProfile.objects.filter(
            user=user, is_verified=True).exists():
        raise PermissionDenied("Your mechanic profile must be verified before submitting content.")


@transaction.atomic
def claim(item, user):
    if _role(user) != "mechanic":
        raise PermissionDenied("Only mechanics can claim AI draft content.")
    if item.created_by_id is not None or item.status not in {Status.AI_DRAFT, Status.DRAFT}:
        raise WorkflowError("Only unassigned draft content can be claimed.")
    item.created_by = user
    if item.status == Status.AI_DRAFT:
        item.status = Status.DRAFT
    item.save(update_fields=["created_by", "status", "updated_at"])
    _log(item, ContentReview.Decision.CLAIMED, user, submitted_by=user,
         snapshot=_snapshot(item))
    return item


@transaction.atomic
def start_review(item, reviewer):
    _require_reviewer(reviewer)
    if _is_revision(item):
        if item.status != ContentRevision.RevisionStatus.SUBMITTED:
            raise WorkflowError("Only submitted content can enter review.")
        item.status = ContentRevision.RevisionStatus.UNDER_REVIEW
        item.save(update_fields=["status"])
        _log(_live(item), ContentReview.Decision.UNDER_REVIEW, reviewer,
             submitted_by=item.author, snapshot={"revision_id": item.pk,
             "base_version": item.base_version, "payload": item.payload},
             version=item.base_version)
        return item
    if item.status != Status.SUBMITTED:
        raise WorkflowError("Only submitted content can enter review.")
    item.status = Status.UNDER_REVIEW
    item.save(update_fields=["status", "updated_at"])
    _log(item, ContentReview.Decision.UNDER_REVIEW, reviewer,
         submitted_by=item.created_by)
    return item


def _require_not_self(item, reviewer, submitter_id=None):
    if (item.created_by_id == reviewer.pk and not
            getattr(settings, "ALLOW_SELF_APPROVAL", False)):
        raise PermissionDenied("You cannot approve your own submission.")
    if (submitter_id == reviewer.pk and not
            getattr(settings, "ALLOW_SELF_APPROVAL", False)):
        raise PermissionDenied("You cannot approve your own submission.")


def approve(item_or_revision, reviewer, comment=""):
    _require_reviewer(reviewer)
    with transaction.atomic():
        if _is_revision(item_or_revision):
            revision = ContentRevision.objects.select_for_update().get(
                pk=item_or_revision.pk)
            live = type(revision.content_object).objects.select_for_update().get(
                pk=revision.object_id)
            _require_not_self(live, reviewer, revision.author_id)
            if revision.status not in {ContentRevision.RevisionStatus.SUBMITTED,
                                       ContentRevision.RevisionStatus.UNDER_REVIEW}:
                raise WorkflowError("Only submitted revisions can be approved.")
            apply_revision(revision, reviewer, comment=comment, _locked=(live, revision))
            revision.status = ContentRevision.RevisionStatus.APPROVED
            revision.save(update_fields=["status"])
            return live
        live = type(item_or_revision).objects.select_for_update().get(pk=item_or_revision.pk)
        _require_not_self(live, reviewer)
        if live.status not in {Status.SUBMITTED, Status.UNDER_REVIEW}:
            raise WorkflowError("Only submitted content can be approved.")
        live.status = Status.APPROVED
        live.approved_by = reviewer
        live.is_dummy = False
        live.save(update_fields=["status", "approved_by", "is_dummy", "updated_at"])
        _log(live, ContentReview.Decision.APPROVED, reviewer,
             submitted_by=live.created_by, comment=comment)
        return live


def _comment_required(comment):
    if not comment or not comment.strip():
        raise WorkflowError("A comment is required for this transition.")


@transaction.atomic
def return_for_changes(item, reviewer, comment):
    _require_reviewer(reviewer)
    _comment_required(comment)
    if _is_revision(item):
        if item.status not in {ContentRevision.RevisionStatus.SUBMITTED,
                               ContentRevision.RevisionStatus.UNDER_REVIEW}:
            raise WorkflowError("Only submitted revisions can be returned.")
        item.status = ContentRevision.RevisionStatus.RETURNED
        item.save(update_fields=["status"])
        _log(_live(item), ContentReview.Decision.RETURNED, reviewer,
             submitted_by=item.author, comment=comment,
             snapshot={"revision_id": item.pk, "base_version": item.base_version,
                       "payload": item.payload}, version=item.base_version)
        return item
    if item.status not in {Status.SUBMITTED, Status.UNDER_REVIEW}:
        raise WorkflowError("Only submitted content can be returned.")
    item.status = Status.DRAFT
    item.save(update_fields=["status", "updated_at"])
    _log(item, ContentReview.Decision.RETURNED, reviewer,
         submitted_by=item.created_by, comment=comment)
    return item


@transaction.atomic
def reject(item, reviewer, comment):
    _require_reviewer(reviewer)
    _comment_required(comment)
    if _is_revision(item):
        if item.status not in {ContentRevision.RevisionStatus.SUBMITTED,
                               ContentRevision.RevisionStatus.UNDER_REVIEW}:
            raise WorkflowError("Only submitted revisions can be rejected.")
        item.status = ContentRevision.RevisionStatus.REJECTED
        item.save(update_fields=["status"])
        _log(_live(item), ContentReview.Decision.REJECTED, reviewer,
             submitted_by=item.author, comment=comment,
             snapshot={"revision_id": item.pk, "base_version": item.base_version,
                       "payload": item.payload}, version=item.base_version)
        return item
    if item.status not in {Status.SUBMITTED, Status.UNDER_REVIEW}:
        raise WorkflowError("Only submitted content can be rejected.")
    item.status = Status.REJECTED
    item.save(update_fields=["status", "updated_at"])
    _log(item, ContentReview.Decision.REJECTED, reviewer,
         submitted_by=item.created_by, comment=comment)
    return item


@transaction.atomic
def reject_ai_draft(item, mechanic, reason):
    """Let a mechanic decline only an unassigned imported AI draft."""
    if _role(mechanic) != "mechanic":
        raise PermissionDenied("Only mechanics can reject an AI draft.")
    _comment_required(reason)
    locked = type(item).objects.select_for_update().get(pk=item.pk)
    if locked.status != Status.AI_DRAFT or locked.created_by_id is not None:
        raise WorkflowError("Only unassigned AI draft content can be rejected.")
    locked.status = Status.REJECTED
    locked.created_by = mechanic
    locked.save(update_fields=["status", "created_by", "updated_at"])
    _log(locked, ContentReview.Decision.REJECTED, mechanic,
         submitted_by=mechanic, comment=reason, reviewed=False,
         snapshot={**_snapshot(locked), "rejection_reason": reason.strip()})
    return locked


@transaction.atomic
def publish(item, reviewer):
    _require_reviewer(reviewer)
    if item.status != Status.APPROVED:
        raise WorkflowError("Only approved content can be published.")
    item.status = Status.PUBLISHED
    item.save(update_fields=["status", "updated_at"])
    _log(item, ContentReview.Decision.PUBLISHED, reviewer,
         submitted_by=item.created_by)
    return item


@transaction.atomic
def create_revision(item, user, payload):
    _owner(item, user)
    if item.status not in {Status.APPROVED, Status.PUBLISHED}:
        raise WorkflowError("Revisions are only for approved or published content.")
    if not isinstance(payload, dict) or not payload:
        raise ValidationError("Revision payload must be a non-empty object.")
    payload = json.loads(json.dumps(payload, cls=DjangoJSONEncoder))
    if isinstance(item, Cause):
        required = {"links", "self_checks", "costs"}
        if not required.issubset(payload):
            raise ValidationError("Cause revisions must include links, self_checks, and costs.")
    if isinstance(item, Question) and "options" not in payload:
        raise ValidationError("Question revisions must include all answer options.")
    ct = ContentType.objects.get_for_model(item)
    revision = ContentRevision.objects.create(
        content_type=ct, object_id=item.pk, base_version=item.version,
        payload=payload, author=user,
    )
    _log(item, ContentReview.Decision.REVISION_CREATED, user,
         submitted_by=user, snapshot={"revision_id": revision.pk,
         "base_version": revision.base_version, "payload": payload},
         version=item.version, reviewed=False)
    return revision


def apply_revision(revision, reviewer, comment="", _locked=None):
    _require_reviewer(reviewer)
    if not _is_revision(revision):
        raise WorkflowError("A content revision is required.")
    if _locked is None:
        with transaction.atomic():
            revision = ContentRevision.objects.select_for_update().get(pk=revision.pk)
            model = revision.content_type.model_class()
            live = model.objects.select_for_update().get(pk=revision.object_id)
            return apply_revision(revision, reviewer, comment,
                                  _locked=(live, revision))
    if _locked:
        live, revision = _locked
    else:
        live = revision.content_object
    _require_not_self(live, reviewer, revision.author_id)
    if live.version != revision.base_version:
        raise WorkflowError("This revision is based on an older content version.")
    if revision.status not in {ContentRevision.RevisionStatus.SUBMITTED,
                               ContentRevision.RevisionStatus.UNDER_REVIEW}:
        raise WorkflowError("Only submitted revisions can be applied.")
    payload = dict(revision.payload)
    nested = {}
    if isinstance(live, Cause):
        nested = {key: payload.pop(key) for key in ("links", "self_checks", "costs")}
        car_models = payload.pop("car_models", None)
    elif isinstance(live, Question):
        nested = {"options": payload.pop("options")}
        car_models = None
    else:
        car_models = None
    fields = {name for field in live._meta.concrete_fields
              for name in (field.name, field.attname)}
    protected = {"id", "pk", "status", "is_dummy", "version", "created_by",
                 "approved_by", "created_by_id", "approved_by_id",
                 "created_at", "updated_at"}
    unknown = payload.keys() - fields
    if unknown:
        raise ValidationError({"payload": f"Unknown fields: {sorted(unknown)}"})
    if payload.keys() & protected:
        raise ValidationError("Workflow fields cannot be changed in a revision payload.")
    with transaction.atomic():
        for key, value in payload.items():
            setattr(live, key, value)
        live.version = max(live.version, revision.base_version) + 1
        live.status = Status.APPROVED
        live.is_dummy = False
        live.approved_by = reviewer
        live.full_clean(exclude=["created_by", "approved_by"])
        live.save()
        if isinstance(live, Cause):
            if car_models is not None:
                from garage.models import CarModel
                live.car_models.set(CarModel.objects.filter(pk__in=car_models))
            _replace_cause_children(live, nested, reviewer, revision.author)
        elif isinstance(live, Question):
            _replace_question_options(live, nested["options"])
        _log(live, ContentReview.Decision.APPROVED, reviewer,
             submitted_by=revision.author, comment=comment,
             snapshot={**_snapshot(live), "revision_id": revision.pk,
                       "base_version": revision.base_version})
    return live


def _replace_cause_children(cause, nested, reviewer, author):
    from garage.models import CarModel
    from knowledge.models import Symptom

    links = nested["links"]
    checks = nested["self_checks"]
    costs = nested["costs"]
    if not all(isinstance(x, dict) for group in (links, checks, costs) for x in group):
        raise ValidationError("Nested cause content must be lists of objects.")
    link_objs = []
    for row in links:
        symptom = Symptom.objects.get(pk=row["symptom"])
        car_model_id = row.get("car_model")
        car_model = CarModel.objects.get(pk=car_model_id) if car_model_id else None
        link = CauseSymptomLink(cause=cause, symptom=symptom,
                                strength=row["strength"], car_model=car_model)
        link.full_clean(exclude=["cause"], validate_unique=False,
                        validate_constraints=False)
        link_objs.append(link)
    check_objs = []
    for row in checks:
        obj = SelfCheck(cause=cause, **{k: v for k, v in row.items()
                                        if k in {"steps", "tools_needed", "difficulty"}},
                        status=Status.PUBLISHED, is_dummy=False,
                        created_by=author, approved_by=reviewer)
        obj.full_clean(exclude=["cause", "created_by", "approved_by"],
                       validate_unique=False, validate_constraints=False)
        check_objs.append(obj)
    cost_objs = []
    for row in costs:
        obj = RepairCost(cause=cause, **{k: v for k, v in row.items()
                                         if k in {"city", "parts_min", "parts_max",
                                                  "labour_min", "labour_max",
                                                  "last_verified", "source"}},
                         status=Status.PUBLISHED, is_dummy=False,
                         created_by=author, approved_by=reviewer)
        obj.full_clean(exclude=["cause", "created_by", "approved_by"],
                       validate_unique=False, validate_constraints=False)
        cost_objs.append(obj)
    cause.links.all().delete()
    cause.self_checks.all().delete()
    cause.costs.all().delete()
    for link in link_objs:
        link.save()
    SelfCheck.objects.bulk_create(check_objs)
    RepairCost.objects.bulk_create(cost_objs)


def _replace_question_options(question, options):
    from knowledge.models import Symptom

    if not isinstance(options, list):
        raise ValidationError("Question options must be a list.")
    cleaned = []
    for row in options:
        if not isinstance(row, dict):
            raise ValidationError("Question options must be objects.")
        symptom_id = row.get("implies_symptom_id") or row.get("implies_symptom")
        symptom = Symptom.objects.get(pk=symptom_id) if symptom_id else None
        cleaned.append({"label": row.get("label", ""),
                        "label_roman": row.get("label_roman", ""),
                        "is_unsure": row.get("is_unsure", False),
                        "implies_symptom": symptom})
    Question.validate_option_data(cleaned)
    objects = [AnswerOption(question=question, **row) for row in cleaned]
    for option in objects:
        option.full_clean(exclude=["question"], validate_unique=False,
                          validate_constraints=False)
    question.options.all().delete()
    AnswerOption.objects.bulk_create(objects)
