from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from garage.models import Car
from knowledge.models import (AnswerOption, Cause, CauseSymptomLink, Question,
                              RepairCost, Symptom, ObdCode)

from .models import (DiagnosisSession, Outcome, SessionAnswer, SessionResult,
                     SessionSymptom)

User = get_user_model()


class SessionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionAnswer
        fields = ["id", "question", "option", "free_text", "answered_at"]


class QuestionPayloadSerializer(serializers.ModelSerializer):
    text = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ["id", "text", "type", "media_url", "options"]

    @extend_schema_field(serializers.CharField())
    def get_text(self, obj):
        user = self.context.get("user")
        language = getattr(user, "language", "en")
        return obj.text_roman or obj.text_en if language == "roman_ur" else obj.text_en

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_options(self, obj):
        user = self.context.get("user")
        language = getattr(user, "language", "en")
        return [{"id": option.pk,
                 "label": (option.label_roman or option.label)
                 if language == "roman_ur" else option.label,
                 "is_unsure": option.is_unsure}
                for option in obj.options.all()]


class PreScreenAnswerSerializer(serializers.Serializer):
    question = serializers.IntegerField(min_value=1)
    option = serializers.IntegerField(min_value=1)
    free_text = serializers.CharField(max_length=300, required=False, allow_blank=True)


class SessionCreateSerializer(serializers.Serializer):
    car = serializers.PrimaryKeyRelatedField(queryset=Car.objects.none())
    free_text = serializers.CharField(max_length=2000, required=False,
                                      allow_blank=False, trim_whitespace=True)
    obd_code = serializers.PrimaryKeyRelatedField(
        queryset=ObdCode.objects.all(), required=False)
    pre_screen_answers = serializers.ListField(
        child=PreScreenAnswerSerializer(), required=False, write_only=True,
        max_length=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["car"].queryset = Car.objects.filter(user=request.user)

    def validate_pre_screen_answers(self, answers):
        checked = []
        for index, item in enumerate(answers):
            try:
                question = Question.objects.visible().select_related("symptom").get(
                    pk=item["question"])
                option = AnswerOption.objects.select_related(
                    "question", "implies_symptom").get(pk=item["option"])
            except (Question.DoesNotExist, AnswerOption.DoesNotExist, TypeError, ValueError):
                raise serializers.ValidationError(
                    {index: "A valid question and option are required."})
            if option.question_id != question.pk:
                raise serializers.ValidationError(
                    {index: "The option must belong to the question."})
            if (option.implies_symptom_id and
                    option.implies_symptom.category_id != question.symptom.category_id):
                raise serializers.ValidationError(
                    {index: "The answer symptom must belong to the question category."})
            checked.append({"question": question, "option": option,
                            "free_text": item.get("free_text", "")})
        return checked

    def validate(self, attrs):
        has_text = bool(attrs.get("free_text"))
        has_obd = bool(attrs.get("obd_code"))
        if has_text == has_obd:
            raise serializers.ValidationError(
                "Provide a problem description or an OBD code, not both.")
        return attrs


class AnswerInputSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.visible())
    option = serializers.PrimaryKeyRelatedField(queryset=AnswerOption.objects.all())
    free_text = serializers.CharField(max_length=300, required=False,
                                      allow_blank=True, default="")

    def validate(self, attrs):
        question, option = attrs["question"], attrs["option"]
        if option.question_id != question.id:
            raise serializers.ValidationError(
                {"option": "This option does not belong to that question."})
        session = self.context["session"]
        if question.symptom.category_id != session.category_id:
            raise serializers.ValidationError(
                {"question": "This question is not part of this session's category."})
        if (option.implies_symptom_id and
                option.implies_symptom.category_id != session.category_id):
            raise serializers.ValidationError(
                {"option": "This answer points to a symptom outside this session's category."})
        if option.implies_symptom_id:
            if not Symptom.objects.visible().filter(
                    pk=option.implies_symptom_id).exists():
                raise serializers.ValidationError(
                    {"option": "This answer points to an unavailable symptom."})
            links = (CauseSymptomLink.objects.filter(
                symptom_id=option.implies_symptom_id,
                cause__in=Cause.objects.visible())
                .filter(Q(cause__car_models__isnull=True) |
                        Q(cause__car_models__id=session.car.car_model_id))
                .filter(Q(car_model_id=session.car.car_model_id) |
                        Q(car_model__isnull=True)))
            if session.obd_code_id:
                links = links.filter(
                    cause__obd_code_links__obd_code_id=session.obd_code_id)
            if not links.exists():
                raise serializers.ValidationError({
                    "option": "This answer is not linked to a possible cause in this session."})
        return attrs


class FreeTextInputSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000, trim_whitespace=True,
                                 allow_blank=False)


class RemoveSessionSymptomSerializer(serializers.Serializer):
    symptom = serializers.IntegerField(min_value=1)

    def validate_symptom(self, value):
        session = self.context["session"]
        try:
            return Symptom.objects.visible().get(
                pk=value, category_id=session.category_id,
                session_symptoms__session=session,
                session_symptoms__source=SessionSymptom.Source.FREE_TEXT)
        except Symptom.DoesNotExist as exc:
            raise serializers.ValidationError("This mapped symptom is not in the session.") from exc


class OutcomeSerializer(serializers.ModelSerializer):
    actual_cause = serializers.PrimaryKeyRelatedField(
        queryset=Cause.objects.visible(), required=False, allow_null=True)
    actual_cause_text = serializers.CharField(max_length=200, required=False,
                                              allow_blank=True)
    actual_cost = serializers.IntegerField(min_value=0, max_value=100_000_000,
                                           required=False, allow_null=True)
    mechanic = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="mechanic"), required=False, allow_null=True)
    mechanic_type = serializers.CharField(required=False, allow_blank=True, max_length=120)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    class Meta:
        model = Outcome
        fields = ["id", "actual_cause", "actual_cause_text", "actual_cost",
                  "mechanic", "mechanic_type", "was_helpful", "notes", "created_at"]
        read_only_fields = ["created_at"]
        extra_kwargs = {"was_helpful": {"required": True}}


class DiagnosisSessionSerializer(serializers.ModelSerializer):
    answers = SessionAnswerSerializer(many=True, read_only=True)
    results = serializers.SerializerMethodField()
    has_outcome = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_results(self, obj):
        return [{"cause": result.cause_id, "cause_name": result.cause_name,
                 "rank": result.rank, "confidence": result.confidence}
                for result in obj.results.all()]

    @extend_schema_field(serializers.BooleanField())
    def get_has_outcome(self, obj):
        return hasattr(obj, "outcome")

    class Meta:
        model = DiagnosisSession
        fields = ["id", "car", "category", "diagnosis_type", "obd_code",
                  "status", "safety_alert", "free_text",
                  "started_at", "completed_at", "answers", "results", "has_outcome"]
        read_only_fields = ["status", "safety_alert", "started_at", "completed_at"]
