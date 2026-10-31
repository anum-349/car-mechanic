import json
import os
from pathlib import Path
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from knowledge.api import DraftContentResponseMixin
from knowledge.models import (AnswerEffect, Cause, Question, RepairCost, SelfCheck,
                              Symptom, SymptomCategory)

from .engine import (context_facts, evidence,
                     next_question as choose_next_question, rank_causes,
                     safety_alert, should_stop)
from .models import (DiagnosisSession, Outcome, SessionAnswer, SessionContextFact, SessionResult,
                     SessionSymptom)
from .serializers import (AnswerInputSerializer, DiagnosisSessionSerializer,
                          FreeTextInputSerializer, OutcomeSerializer,
                          QuestionPayloadSerializer,
                          RemoveSessionSymptomSerializer,
                          SessionCreateSerializer)
from .tasks import send_outcome_reminder
from analytics.services import emit, record_result_viewed, track_question_asked
from .nlu import classify_category, infer_text_category, keyword_symptoms, map_text_to_symptoms, resolve_text_context

logger = logging.getLogger(__name__)

def _copy_templates():
    path = Path(settings.BASE_DIR) / "knowledge" / "data" / "diagnosis_copy.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _message(alert, language):
    symptom = alert["symptom"]
    label = (symptom.text_roman or symptom.text_en) if language == "roman_ur" else symptom.text_en
    if language == "roman_ur":
        return f"Aap ki safety ke liye, {label} ki wajah se gari na chalayein aur mechanic ya tow service se rabta karein."
    return f"For your safety, do not drive because of {label}. Contact a mechanic or towing service."

def _band(confidence):
    value = float(confidence)
    if value >= settings.ENGINE_BAND_VERY_LIKELY:
        return "very likely"
    if value >= settings.ENGINE_BAND_LIKELY:
        return "likely"
    if value >= settings.ENGINE_BAND_POSSIBLE:
        return "possible"
    return "unlikely"

def _text_diagnostic_context(text):
    category, mapped = resolve_text_context(text)
    if category is not None and not Question.objects.visible().filter(
            symptom__category=category).exists():
        return None, []
    return category, mapped
   
def _obd_diagnostic_context(code):
    causes = Cause.objects.visible().filter(obd_code_links__obd_code=code)
    symptoms = Symptom.objects.visible().filter(
        links__cause__in=causes, is_observable=True, is_generic=False).distinct()
    categories = list(SymptomCategory.objects.filter(
        symptoms__in=symptoms).annotate(
            symptom_count=Count("symptoms", distinct=True)
        ).order_by("-symptom_count", "id"))
    if not causes.exists() or not categories:
        return None
    if len(categories) > 1 and categories[0].symptom_count == categories[1].symptom_count:
        return None
    return categories[0]


class DiagnosisSessionViewSet(DraftContentResponseMixin, mixins.ListModelMixin,
                              mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = DiagnosisSession.objects.none()
    serializer_class = DiagnosisSessionSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "diagnosis"

    @extend_schema(parameters=[OpenApiParameter(
        name="car", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY)],
        responses=DiagnosisSessionSerializer(many=True))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        return (DiagnosisSession.objects.filter(user=self.request.user)
                .select_related("car__car_model", "category", "obd_code")
                .select_related("outcome")
                .prefetch_related("answers__option", "answers__question__symptom",
                                  "answers__question__options", "results",
                                  "session_symptoms__symptom")
                .order_by("-started_at"))

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        car_id = self.request.query_params.get("car")
        if car_id:
            try:
                parsed_car_id = int(car_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"car": "A valid car id is required."}) from exc
            if parsed_car_id < 1:
                raise ValidationError({"car": "A valid car id is required."})
            queryset = queryset.filter(car_id=parsed_car_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return SessionCreateSerializer
        return super().get_serializer_class()

    @extend_schema(responses={200: dict})
    def retrieve(self, request, *args, **kwargs):
        """Resume an owned session at its next question or return its result."""
        session = self.get_object()
        base = DiagnosisSessionSerializer(session).data
        base["understood_symptoms"] = [{
            "id": item.symptom_id,
            "text": (item.symptom.text_roman or item.symptom.text_en)
            if request.user.language == "roman_ur" else item.symptom.text_en,
        } for item in session.session_symptoms.filter(
            source=SessionSymptom.Source.FREE_TEXT).select_related("symptom")]
        base["conversation"] = [{
            "question": self._question_data(answer.question, request.user),
            "answer": {
                "id": answer.option_id,
                "label": (answer.option.label_roman or answer.option.label)
                if request.user.language == "roman_ur" else answer.option.label,
            },
        } for answer in session.answers.all().order_by("id")]
        base["diagnosis_type"] = session.diagnosis_type
        if session.obd_code_id:
            base["obd_context"] = {
                "code": session.obd_code.code,
                "description": session.obd_code.description,
                "system": session.obd_code.system,
            }
        if session.status == DiagnosisSession.Status.ABANDONED:
            return Response({**base, "done": True,
                             "result": self._ranked_payload(session, [])})
        if session.category_id is None:
            if session.diagnosis_type == "text":
                category, mapped = _text_diagnostic_context(session.free_text)
                if category is None:
                    return Response({**base, "done": False,
                                     "clarification_required": True})
                session.category = category
                session.save(update_fields=["category"])
                SessionSymptom.objects.bulk_create([
                    SessionSymptom(session=session, symptom=symptom,
                                   source=SessionSymptom.Source.FREE_TEXT)
                    for symptom in mapped
                ], ignore_conflicts=True)
                base["category"] = category.pk
                base["understood_symptoms"] = [{
                    "id": symptom.pk,
                    "text": (symptom.text_roman or symptom.text_en)
                    if request.user.language == "roman_ur" else symptom.text_en,
                } for symptom in mapped]
            else:
                return Response({**base, "done": True,
                                 "result": self._ranked_payload(session, [])})
        alert = safety_alert(session)
        base["context"] = context_facts(session)
        if alert:
            return Response({**base, "stop": True,
                             "message": _message(alert, request.user.language),
                             "message_key": alert["message_key"]})
        if session.status == DiagnosisSession.Status.COMPLETED:
            stored = {result.cause_id: result for result in session.results.all()}
            ranked = [item for item in rank_causes(session, top=5)
                      if item["cause"].pk in stored]
            payload = self._ranked_payload(session, ranked)
            for row, item in zip(payload["results"], ranked):
                row["cause_name"] = stored[item["cause"].pk].cause_name
            return Response({**base, "done": True, "result": payload})
        if session.status == DiagnosisSession.Status.IN_PROGRESS:
            ranked = rank_causes(session, top=3)
            question = choose_next_question(session, ranked)
            if question:
                track_question_asked(session, question)
                return Response({**base, "done": False,
                                 "question": self._question_data(question, request.user)})
            self._persist_completion(session, ranked)
            return Response({**base, "done": True,
                             "result": self._ranked_payload(
                                 session, rank_causes(session, top=5))})
        return Response({**base, "done": True,
                         "result": self._ranked_payload(session, [])})

    def _question_data(self, question, user):
        if not question:
            return None
        return QuestionPayloadSerializer(question, context={"user": user}).data

    @extend_schema(request=SessionCreateSerializer, responses={201: DiagnosisSessionSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        diagnosis_type = "obd" if values.get("obd_code") else "text"
        category = None
        mapped = []
        if diagnosis_type == "text":
            category, mapped = _text_diagnostic_context(values["free_text"])
        else:
            category = _obd_diagnostic_context(values["obd_code"])
        with transaction.atomic():
            session = DiagnosisSession.objects.create(
                user=request.user, car=values["car"], category=category,
                diagnosis_type=diagnosis_type, obd_code=values.get("obd_code"),
                free_text=values.get("free_text", ""),
                mechanic_reporter=(request.user if request.user.role == "mechanic"
                                   else None))
            emit("session_started", user=request.user, session=session,
                 props={"category_id": session.category_id,
                        "diagnosis_type": diagnosis_type})
            if diagnosis_type == "text" and category is None:
                return Response({
                    "id": session.pk, "diagnosis_type": diagnosis_type,
                    "clarification_required": True,
                }, status=status.HTTP_201_CREATED)
            if diagnosis_type == "obd" and category is None:
                self._persist_completion(session, [])
                result = self._ranked_payload(session, [])
                return Response({
                    "id": session.pk, "diagnosis_type": diagnosis_type,
                    "obd_context": {"code": session.obd_code.code,
                                    "description": session.obd_code.description,
                                    "system": session.obd_code.system},
                    "done": True, "result": result,
                }, status=status.HTTP_201_CREATED)
            SessionSymptom.objects.bulk_create([
                SessionSymptom(session=session, symptom=symptom,
                               source=SessionSymptom.Source.FREE_TEXT)
                for symptom in mapped
            ])
            for answer in values.get("pre_screen_answers", []):
                current_ranked = rank_causes(session, top=3)
                expected_question = choose_next_question(session, current_ranked)
                if (expected_question is None or
                        expected_question.pk != answer["question"].pk):
                    raise ValidationError({
                        "pre_screen_answers":
                            "Answers must follow the session's current question order."})
                answer_serializer = AnswerInputSerializer(
                    data={"question": answer["question"].pk,
                          "option": answer["option"].pk,
                          "free_text": answer.get("free_text", "")},
                    context={"session": session})
                answer_serializer.is_valid(raise_exception=True)
                saved_answer = SessionAnswer.objects.create(
                    session=session, **answer_serializer.validated_data)
                track_question_asked(session, answer["question"])
                self.record_context(session, saved_answer)
            alert = safety_alert(session)
            if alert:
                session.safety_alert = True
                session.save(update_fields=["safety_alert"])
                return Response({"id": session.pk, "stop": True,
                                 "message": _message(alert, request.user.language),
                                 "message_key": alert["message_key"]}, status=201)
            ranked = rank_causes(session, top=3)
            question = choose_next_question(session, ranked)
            if question:
                track_question_asked(session, question)
            if question is None:
                self._persist_completion(session, ranked)
        response = {"id": session.pk, "diagnosis_type": diagnosis_type,
                    "done": question is None}
        if diagnosis_type == "obd":
            response["obd_context"] = {
                "code": session.obd_code.code,
                "description": session.obd_code.description,
                "system": session.obd_code.system,
            }
        if question:
            response["question"] = self._question_data(question, request.user)
        else:
            response["result"] = self._ranked_payload(
                session, rank_causes(session, top=5))
        return Response(response, status=status.HTTP_201_CREATED)

    @extend_schema(request=FreeTextInputSerializer, responses={200: dict})
    @action(detail=True, methods=["post", "delete"], url_path="free-text",
            throttle_scope="free_text")
    def free_text(self, request, pk=None):
        with transaction.atomic():
            session = self._locked_session(request, pk)
            if session.status != DiagnosisSession.Status.IN_PROGRESS:
                return Response({"detail": "Only an in-progress session accepts symptom changes."},
                                status=400)
            if session.diagnosis_type == "obd":
                return Response(
                    {"detail": "OBD diagnosis sessions do not accept problem descriptions."},
                    status=400)
            if request.method == "DELETE":
                serializer = RemoveSessionSymptomSerializer(
                    data=request.data, context={"session": session})
                serializer.is_valid(raise_exception=True)
                serializer.validated_data["symptom"].session_symptoms.filter(
                    session=session,
                    source=SessionSymptom.Source.FREE_TEXT).delete()
                return Response({"removed": True, "symptom": request.data["symptom"]})

            serializer = FreeTextInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            if session.category_id is not None or session.answers.exists():
                return Response(
                    {"detail": "Clarification is only accepted before diagnostic questions begin."},
                    status=400)
            clarification = serializer.validated_data["text"]
            text = "\n".join(part for part in (session.free_text, clarification) if part)
            category, mapped = _text_diagnostic_context(text)
            session.free_text = text
            session.save(update_fields=["free_text"])
            session.session_symptoms.filter(
                source=SessionSymptom.Source.FREE_TEXT).delete()
            if category is None:
                return Response({"clarification_required": True})
            session.category = category
            session.save(update_fields=["category"])
            SessionSymptom.objects.bulk_create([
                SessionSymptom(session=session, symptom=symptom,
                               source=SessionSymptom.Source.FREE_TEXT)
                for symptom in mapped
            ])
            ranked = rank_causes(session, top=3)
            question = choose_next_question(session, ranked)
            if question:
                track_question_asked(session, question)
            else:
                self._persist_completion(session, ranked)
            alert = safety_alert(session)
            if alert:
                session.safety_alert = True
                session.save(update_fields=["safety_alert"])
        if alert:
            return Response({"stop": True, "safety_alert": True,
                             "message": _message(alert, request.user.language),
                             "message_key": alert["message_key"], "mapped": [
                                 {"id": item.pk,
                                  "text": item.text_roman or item.text_en
                                  if request.user.language == "roman_ur"
                                  else item.text_en} for item in mapped],
                             "fallback": not bool(mapped)})
        if question:
            return Response({"mapped": [{
                "id": item.pk,
                "text": (item.text_roman or item.text_en)
                if request.user.language == "roman_ur" else item.text_en,
            } for item in mapped], "question": self._question_data(
                question, request.user), "done": False})
        return Response({"mapped": [{
            "id": item.pk,
            "text": (item.text_roman or item.text_en)
            if request.user.language == "roman_ur" else item.text_en,
        } for item in mapped], "done": True, "result": self._ranked_payload(
            session, rank_causes(session, top=5))})

    @staticmethod
    def _locked_session(request, pk):
        session = (DiagnosisSession.objects.select_for_update()
                   .filter(pk=pk, user=request.user).first())
        if session is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        return session

    @staticmethod
    def _persist_completion(session, ranked):
        if session.status == DiagnosisSession.Status.COMPLETED:
            return
        observations = evidence(session)
        if not observations["present"] and not observations["absent"]:
            ranked = []
        if not session.results.exists():
            SessionResult.objects.bulk_create([
                SessionResult(session=session, cause=item["cause"],
                              cause_name=item["cause"].name, rank=item["rank"],
                              confidence=item["confidence"],
                              explanation=item["explanation"])
                for item in ranked
            ])
        session.status = DiagnosisSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save(update_fields=["status", "completed_at"])
        emit("session_completed", user_id=session.user_id, session=session)
        send_outcome_reminder.apply_async(args=[session.pk], countdown=24 * 60 * 60)

    @staticmethod
    def _ranked_payload(session, ranked):
        copy = _copy_templates()
        observations = evidence(session)
        if not observations["present"] and not observations["absent"]:
            ranked = []
        language = session.user.language
        script_template = copy["ask_mechanic"]["roman_ur" if language == "roman_ur" else "en"]
        city = session.user.city
        results = []
        for item in ranked[:5]:
            cause = item["cause"]
            checks = list(SelfCheck.objects.visible().filter(cause=cause).values(
                "steps", "tools_needed", "difficulty", "status", "is_dummy"))
            costs = RepairCost.objects.visible().filter(cause=cause)
            local_cost = costs.filter(city__iexact=city).first() if city else None
            cost = local_cost or costs.order_by("id").first()
            cost_data = None
            related_draft = any(check["is_dummy"] or check["status"] == "ai_draft"
                                for check in checks)
            if cost:
                cost_data = {
                    "city": cost.city, "city_fallback": not bool(local_cost),
                    "parts_min": cost.parts_min, "parts_max": cost.parts_max,
                    "labour_min": cost.labour_min, "labour_max": cost.labour_max,
                    "total_min": cost.parts_min + cost.labour_min,
                    "total_max": cost.parts_max + cost.labour_max,
                    "currency": "PKR", "last_verified": cost.last_verified,
                    "source": cost.source,
                }
                related_draft = related_draft or cost.is_dummy or cost.status == "ai_draft"
            for check in checks:
                check.pop("status", None)
                check.pop("is_dummy", None)
            name = cause.name
            results.append({
                "cause": cause.pk, "cause_name": name, "rank": item["rank"],
                "confidence": item["confidence"], "band": _band(item["confidence"]),
                "explanation": item["explanation"],
                "why": {"supporting": item["supporting_symptoms"],
                        "contradicting": item["contradicting_symptoms"],
                        "missing": item["missing_symptoms"]},
                "severity": cause.severity, "safe_to_drive": cause.safe_to_drive,
                "self_checks": checks, "cost": cost_data,
                "ask_your_mechanic": script_template.format(cause=name),
                "draft_content": cause.is_dummy or cause.status == "ai_draft" or
                    related_draft,
            })
        payload = {"id": session.pk, "status": session.status,
                "diagnosis_type": session.diagnosis_type,
                "obd_code": session.obd_code.code if session.obd_code_id else None,
                "free_text": session.free_text if session.diagnosis_type == "text" else "",
                "answers": [{
                    "question": (answer.question.text_roman or answer.question.text_en)
                    if language == "roman_ur" else answer.question.text_en,
                    "answer": (answer.option.label_roman or answer.option.label)
                    if language == "roman_ur" else answer.option.label,
                    "effect": answer.option.effect,
                } for answer in session.answers.select_related(
                    "question", "option").order_by("answered_at", "id")],
                "results": results,
                "ask_your_mechanic": {
                    "en": copy["ask_mechanic"]["en"].format(
                        cause=results[0]["cause_name"] if results else "a possible cause"),
                    "roman_ur": copy["ask_mechanic"]["roman_ur"].format(
                        cause=results[0]["cause_name"] if results else "mumkin wajah"),
                },
                "disclaimer": copy["disclaimer"]["roman_ur" if language == "roman_ur" else "en"],
                "draft_content": any(result["draft_content"] for result in results)}
        if session.obd_code_id:
            payload["obd_context"] = {
                "code": session.obd_code.code,
                "description": session.obd_code.description,
                "system": session.obd_code.system,
            }
        if not results:
            if session.obd_code_id:
                payload["message"] = (
                    "This OBD code has insufficient linked diagnostic data to "
                    "identify a cause. A mechanic should inspect the vehicle."
                    if language != "roman_ur" else
                    "Is OBD code ke saath wajah maloom karne ke liye kaafi "
                    "tashkheesi maloomat nahi. Mechanic se gari check karwayein."
                )
            else:
                payload["message"] = (
                    "Available evidence is insufficient to identify a cause. "
                    "A mechanic should inspect the vehicle."
                    if language != "roman_ur" else
                    "Maujood maloomat se wajah yaqini taur par maloom nahi ho saki. "
                    "Mechanic se gari check karwayein."
                )
        return payload

    @staticmethod
    def record_context(session, answer):
        """Call right after SessionAnswer.objects.create(...)."""
        option = answer.option
        if option.context_key and option.context_value and option.effect not in (
            AnswerEffect.UNSURE, AnswerEffect.DENIES):  # noqa: F821
            SessionContextFact.objects.get_or_create(  # noqa: F821
                session=session, key=option.context_key, value=option.context_value,
                defaults={"answer": answer, "source": "answer"})

    @extend_schema(request=AnswerInputSerializer, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="answer")
    def answer(self, request, pk=None):
        with transaction.atomic():
            session = self._locked_session(request, pk)
            serializer = AnswerInputSerializer(data=request.data,
                                               context={"session": session})
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            if SessionAnswer.objects.filter(session=session,
                                            question=values["question"]).exists():
                return Response({"detail": "This question was already answered."},
                                status=409)
            if session.status != DiagnosisSession.Status.IN_PROGRESS:
                return Response({"detail": f"This session is already {session.status}."},
                                status=400)
            ranked = rank_causes(session, top=5)
            expected_question = choose_next_question(session, ranked)
            if (expected_question is None or
                    expected_question.pk != values["question"].pk):
                raise ValidationError(
                    {"question": "This is not the current question for this session."})
            answer = SessionAnswer.objects.create(session=session, **values)
            self.record_context(session, answer)

            alert = safety_alert(session, current_answer=answer)
            if alert:
                session.safety_alert = True
                session.save(update_fields=["safety_alert"])
                return Response({"stop": True, "safety_alert": True,
                                 "message": _message(alert, request.user.language),
                                 "message_key": alert["message_key"]})
            ranked = rank_causes(session, top=5)
            if should_stop(session, ranked):
                self._persist_completion(session, ranked)
                return Response({"done": True, "safety_alert": False,
                                 "result": self._ranked_payload(session, ranked)})
            question = choose_next_question(session, ranked[:3])
            if question:
                track_question_asked(session, question)
            return Response({"done": False, "safety_alert": False,
                             "question": self._question_data(question, request.user)})

    @extend_schema(responses={200: dict})
    @action(detail=True, methods=["get"], url_path="result")
    def result(self, request, pk=None):
        session = self.get_object()
        if session.safety_alert:
            alert = safety_alert(session)
            if alert:
                return Response({"stop": True,
                                 "message": _message(alert, request.user.language),
                                 "message_key": alert["message_key"]})
        if session.status != DiagnosisSession.Status.COMPLETED:
            return Response({"detail": "The diagnosis is not complete."}, status=400)
        ranked = rank_causes(session, top=5)
        stored = {result.cause_id: result for result in session.results.all()}
        ranked = [item for item in ranked if item["cause"].pk in stored]
        payload = self._ranked_payload(session, ranked)
        for row, item in zip(payload["results"], ranked):
            row["cause_name"] = stored[item["cause"].pk].cause_name
        cost_ranges = [{"cause_id": row["cause"], "min": row["cost"]["total_min"],
                        "max": row["cost"]["total_max"]}
                       for row in payload["results"] if row.get("cost")]
        record_result_viewed(session, request.user, cost_ranges)
        return Response(payload)

    @extend_schema(request=OutcomeSerializer, responses={201: OutcomeSerializer})
    @action(detail=True, methods=["get", "post", "patch"], url_path="outcome")
    def outcome(self, request, pk=None):
        session = self.get_object()
        if request.method == "GET":
            outcome = getattr(session, "outcome", None)
            # #region agent log
            try:
                import json, time
                from pathlib import Path
                _has = Outcome.objects.filter(session_id=session.pk).exists()
                with Path(os.getenv("LOG_PATH")).open("a", encoding="utf-8") as _f:
                    _f.write(json.dumps({
                        "sessionId": "5fc7e1", "runId": "pre-fix", "hypothesisId": "B",
                        "location": "diagnosis/views.py:outcome:GET",
                        "message": "GET outcome handler reached",
                        "data": {
                            "pk": str(pk), "session_id": session.pk,
                            "session_status": session.status,
                            "getattr_none": outcome is None,
                            "outcome_row_exists": _has,
                            "will_status": 404 if outcome is None else 200,
                        },
                        "timestamp": int(time.time() * 1000),
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            if outcome is None:
                empty = {
                    "id": None, "actual_cause": None, "actual_cause_text": "",
                    "actual_cost": None, "mechanic": None, "mechanic_type": "",
                    "was_helpful": None, "notes": "", "created_at": None,
                }
                # #region agent log
                try:
                    import json, time
                    from pathlib import Path
                    with Path(r"C:\Users\akraj\Documents\Car Mechanic\debug-5fc7e1.log").open("a", encoding="utf-8") as _f:
                        _f.write(json.dumps({
                            "sessionId": "5fc7e1", "runId": "post-fix", "hypothesisId": "B",
                            "location": "diagnosis/views.py:outcome:GET:empty",
                            "message": "GET missing outcome returns empty 200",
                            "data": {"pk": str(pk), "session_id": session.pk, "status": 200, "created_row": False},
                            "timestamp": int(time.time() * 1000),
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                return Response(empty, status=200)
            return Response(OutcomeSerializer(outcome).data)
        if request.method == "PATCH":
            if session.status != DiagnosisSession.Status.COMPLETED:
                return Response({"detail": "Complete the diagnosis first."}, status=400)
            if set(request.data) != {"was_helpful"} or not isinstance(
                    request.data.get("was_helpful"), bool):
                return Response({"was_helpful": "Send only a true or false vote."},
                                status=400)
            with transaction.atomic():
                outcome, _ = Outcome.objects.get_or_create(session=session)
                serializer = OutcomeSerializer(
                    outcome, data={"was_helpful": request.data["was_helpful"]},
                    partial=True)
                serializer.is_valid(raise_exception=True)
                outcome = serializer.save()
            return Response(OutcomeSerializer(outcome).data, status=200)
        if session.status != DiagnosisSession.Status.COMPLETED:
            return Response({"detail": "Complete the diagnosis first."}, status=400)
        existing = getattr(session, "outcome", None)
        serializer = OutcomeSerializer(existing, data=request.data, partial=existing is not None)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                outcome = serializer.save(session=session) if existing is None else serializer.save()
        except IntegrityError:
            outcome = Outcome.objects.get(session=session)
        if existing is None:
            emit("outcome_submitted", user=request.user, session=session)
        return Response(OutcomeSerializer(outcome).data,
                        status=201 if existing is None else 200)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="abandon")
    def abandon(self, request, pk=None):
        with transaction.atomic():
            session = self._locked_session(request, pk)
            if session.status != DiagnosisSession.Status.IN_PROGRESS:
                return Response({"detail": "Only an in-progress session can be abandoned."},
                                status=400)
            session.status = DiagnosisSession.Status.ABANDONED
            session.save(update_fields=["status"])
        return Response({"id": session.pk, "status": session.status})

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        with transaction.atomic():
            session = self._locked_session(request, pk)
            if session.safety_alert:
                alert = safety_alert(session)
                if alert:
                    return Response({"safety_alert": True, "stop": True,
                                     "message": _message(alert, request.user.language),
                                     "message_key": alert["message_key"]})
            observations = evidence(session)
            ranked = (rank_causes(session, top=5)
                      if observations["present"] or observations["absent"] else [])
            self._persist_completion(session, ranked)
        payload = self._ranked_payload(session, ranked)
        payload["results"] = [dict(result, estimated_cost=(
            {"min": result["cost"]["total_min"], "max": result["cost"]["total_max"],
             "currency": "PKR", "city": result["cost"]["city"], "is_estimate": True}
            if result["cost"] else None)) for result in payload["results"]]
        payload.update({"safety_alert": session.safety_alert,
                        "completed_at": session.completed_at})
        if not ranked:
            payload["message"] = "Not enough information to rank causes. Please see a mechanic."
        return Response(payload)

    # Retain the previous API actions while clients transition to answer/result.
    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["get"], url_path="next-question")
    def next_question(self, request, pk=None):
        session = self.get_object()
        alert = safety_alert(session)
        if alert:
            return Response({"done": True, "stop": True,
                            "message": _message(alert, request.user.language),
                            "message_key": alert["message_key"]})
        ranked = rank_causes(session, top=5)
        question = choose_next_question(session, ranked)
        if question:
            track_question_asked(session, question)
        return Response({"done": question is None,
                        "question": self._question_data(question, request.user)})