from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (AnswerOption, Cause, CauseSymptomLink, ContentReview,
                     ObdCode, Question, RepairCost, SelfCheck, Symptom,
                     SymptomCategory, WarningLight)

# Set by the workflow endpoints, never by the client.
GOVERNED_READ_ONLY = ["status", "is_dummy", "version", "created_by", "approved_by",
                      "created_at", "updated_at"]


class SymptomCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SymptomCategory
        fields = "__all__"


class SymptomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Symptom
        fields = "__all__"
        read_only_fields = GOVERNED_READ_ONLY


class NestedLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CauseSymptomLink
        fields = ["id", "symptom", "strength"]


class CauseSerializer(serializers.ModelSerializer):
    description = serializers.CharField(max_length=5000, required=False,
                                        allow_blank=True)
    proof_hint = serializers.CharField(max_length=2000, required=False,
                                       allow_blank=True)
    symptom_links = NestedLinkSerializer(source="links", many=True,
                                         read_only=True)

    class Meta:
        model = Cause
        fields = "__all__"
        read_only_fields = GOVERNED_READ_ONLY


class CauseSymptomLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CauseSymptomLink
        fields = "__all__"
        read_only_fields = ["weight"]


class PublicAnswerOptionSerializer(serializers.ModelSerializer):
    """What the app shows a user. Hides implies_symptom (the scoring logic)."""
    class Meta:
        model = AnswerOption
        fields = ["id", "label", "label_roman", "is_unsure"]


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = "__all__"


class QuestionOptionInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ["label", "label_roman", "is_unsure", "implies_symptom"]


@extend_schema_field(serializers.ListField(child=serializers.DictField()))
class QuestionOptionsField(serializers.Field):
    def to_representation(self, value):
        return PublicAnswerOptionSerializer(value.all(), many=True).data

    def to_internal_value(self, data):
        if not isinstance(data, list) or len(data) > 20:
            raise serializers.ValidationError("Provide between 2 and 20 options.")
        option_serializer = QuestionOptionInputSerializer(data=data, many=True)
        option_serializer.is_valid(raise_exception=True)
        return option_serializer.validated_data


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionsField(required=False)

    class Meta:
        model = Question
        fields = "__all__"
        read_only_fields = GOVERNED_READ_ONLY

    def validate(self, attrs):
        options = attrs.get("options")
        if options is not None:
            try:
                Question.validate_option_data(options)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"options": exc.messages}) from exc
        elif self.instance is None:
            raise serializers.ValidationError({
                "options": "At least two options including exactly one unsure option are required."
            })
        return attrs

    def create(self, validated_data):
        options = validated_data.pop("options")
        question = super().create(validated_data)
        AnswerOption.objects.bulk_create([
            AnswerOption(question=question, **option) for option in options
        ])
        return question

    def update(self, instance, validated_data):
        options = validated_data.pop("options", None)
        question = super().update(instance, validated_data)
        if options is not None:
            question.options.all().delete()
            AnswerOption.objects.bulk_create([
                AnswerOption(question=question, **option) for option in options
            ])
        return question


class SelfCheckSerializer(serializers.ModelSerializer):
    steps = serializers.CharField(max_length=5000)

    class Meta:
        model = SelfCheck
        fields = "__all__"
        read_only_fields = GOVERNED_READ_ONLY


class RepairCostSerializer(serializers.ModelSerializer):
    is_estimate = serializers.BooleanField(read_only=True, default=True)
    parts_min = serializers.IntegerField(min_value=0, max_value=100_000_000)
    parts_max = serializers.IntegerField(min_value=0, max_value=100_000_000)
    labour_min = serializers.IntegerField(min_value=0, max_value=100_000_000)
    labour_max = serializers.IntegerField(min_value=0, max_value=100_000_000)

    class Meta:
        model = RepairCost
        fields = "__all__"
        read_only_fields = GOVERNED_READ_ONLY

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["is_estimate"] = True  # costs are always estimates
        return data

    def validate(self, attrs):
        parts_min = attrs.get("parts_min", getattr(self.instance, "parts_min", 0))
        parts_max = attrs.get("parts_max", getattr(self.instance, "parts_max", 0))
        labour_min = attrs.get("labour_min", getattr(self.instance, "labour_min", 0))
        labour_max = attrs.get("labour_max", getattr(self.instance, "labour_max", 0))
        if parts_min > parts_max:
            raise serializers.ValidationError({"parts_max": "Must be at least parts_min."})
        if labour_min > labour_max:
            raise serializers.ValidationError({"labour_max": "Must be at least labour_min."})
        return attrs


class WarningLightSerializer(serializers.ModelSerializer):
    meaning = serializers.CharField(max_length=2000)
    recommended_action = serializers.CharField(max_length=2000)
    meaning_roman = serializers.CharField(max_length=2000, required=False,
                                          allow_blank=True)
    action_roman = serializers.CharField(max_length=2000, required=False,
                                         allow_blank=True)
    class Meta:
        model = WarningLight
        fields = "__all__"
        read_only_fields = ["is_dummy"]


class ObdCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObdCode
        fields = "__all__"


class PublicObdCodeSerializer(serializers.ModelSerializer):
    likely_causes = serializers.SerializerMethodField()
    severity = serializers.SerializerMethodField()
    draft_content = serializers.SerializerMethodField()

    class Meta:
        model = ObdCode
        fields = ["code", "description", "system", "severity",
                  "likely_causes", "draft_content"]

    def _visible_causes(self, obj):
        from .models import Cause
        return Cause.objects.visible().filter(
            obd_code_links__obd_code=obj).distinct()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_likely_causes(self, obj):
        return [{"name": cause.name, "severity": cause.severity}
                for cause in self._visible_causes(obj)]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_severity(self, obj):
        rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        severities = [cause["severity"] for cause in self.get_likely_causes(obj)]
        return max(severities, key=lambda value: rank.get(value, 0), default=None)

    @extend_schema_field(serializers.BooleanField())
    def get_draft_content(self, obj):
        return any(cause.status == "ai_draft" or cause.is_dummy
                   for cause in self._visible_causes(obj))


class ContentReviewSerializer(serializers.ModelSerializer):
    model = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = ContentReview
        fields = ["id", "model", "object_id", "version", "status",
                  "submitted_by", "reviewed_by", "comment", "snapshot",
                  "created_at", "reviewed_at"]

