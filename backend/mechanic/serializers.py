from rest_framework import serializers

from accounts.models import MechanicProfile, User
from accounts.serializers import (MechanicRegistrationResponseSerializer,
                                  MechanicRegistrationSerializer)
from garage.models import CarModel
from knowledge.importer import ImportErrorInFile, validate_flow
from knowledge.models import AnswerOption, Question, SymptomCategory
from knowledge.serializers import (
    AnswerOptionSerializer, CauseSerializer, CauseSymptomLinkSerializer,
    QuestionSerializer, RepairCostSerializer, SelfCheckSerializer,
    SymptomSerializer,
)


class MechanicSelfProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", max_length=20,
                                  required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = MechanicProfile
        fields = ["user", "workshop_name", "address", "city", "phone", "experience_years",
                  "specialization", "is_verified", "honesty_score",
                  "created_at", "updated_at"]
        read_only_fields = ["user", "is_verified", "honesty_score", "created_at",
                            "updated_at"]

    def validate_phone(self, value):
        if value and User.objects.exclude(pk=self.instance.user_id).filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value or None

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "phone" in user_data:
            instance.user.phone = user_data["phone"]
            instance.user.save(update_fields=["phone"])
        return super().update(instance, validated_data)


class FlowInputSerializer(serializers.Serializer):
    """Accept the import-flow JSON format and reuse its structural validation."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Flow must be a JSON object.")
        self.initial_data = data
        return data

    def validate(self, attrs):
        def check_status(value, path="$", errors=None):
            errors = errors if errors is not None else []
            if isinstance(value, dict):
                if "status" in value and value["status"] not in {"draft", "submitted"}:
                    errors.append(f"{path}.status: mechanics may only write draft or submitted content")
                for key, child in value.items():
                    check_status(child, f"{path}.{key}", errors)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    check_status(child, f"{path}[{index}]", errors)
            return errors

        status_errors = check_status(attrs)
        if status_errors:
            raise serializers.ValidationError({"status": status_errors})
        try:
            validate_flow(attrs)
        except ImportErrorInFile as exc:
            raise serializers.ValidationError({"flow": exc.errors}) from exc
        return attrs


class SimulationAnswerSerializer(serializers.Serializer):
    question = serializers.IntegerField(min_value=1)
    option = serializers.IntegerField(min_value=1)
    free_text = serializers.CharField(max_length=300, required=False, allow_blank=True)


class SimulationInputSerializer(serializers.Serializer):
    car_model_id = serializers.PrimaryKeyRelatedField(
        source="car_model", queryset=CarModel.objects.all())
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=SymptomCategory.objects.all())
    answers = SimulationAnswerSerializer(many=True, required=False, default=list,
                                        max_length=50)
    include_drafts = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        rows = []
        category = attrs["category"]
        for index, entry in enumerate(attrs.get("answers", [])):
            try:
                question = Question.objects.select_related("symptom").get(
                    pk=entry["question"])
                option = AnswerOption.objects.select_related(
                    "question", "implies_symptom").get(pk=entry["option"])
            except (Question.DoesNotExist, AnswerOption.DoesNotExist) as exc:
                raise serializers.ValidationError({
                    "answers": {index: "Question or answer option was not found."}}) from exc
            if option.question_id != question.pk:
                raise serializers.ValidationError({
                    "answers": {index: "The option must belong to its question."}})
            if question.symptom.category_id != category.pk:
                raise serializers.ValidationError({
                    "answers": {index: "The question must belong to the selected problem."}})
            if option.implies_symptom_id and option.implies_symptom.category_id != category.pk:
                raise serializers.ValidationError({
                    "answers": {index: "The answer symptom must belong to the selected problem."}})
            rows.append({"question": question, "option": option,
                         "free_text": entry.get("free_text", "")})
        attrs["answers"] = rows
        return attrs


class AiDraftRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, trim_whitespace=True)

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("Please give a reason for rejecting this draft.")
        return value


ITEM_SERIALIZERS = {
    "symptoms": SymptomSerializer,
    "causes": CauseSerializer,
    "links": CauseSymptomLinkSerializer,
    "self-checks": SelfCheckSerializer,
    "repair-costs": RepairCostSerializer,
    "questions": QuestionSerializer,
    "options": AnswerOptionSerializer,
}


def item_serializer(item_type, *args, **kwargs):
    try:
        serializer_class = ITEM_SERIALIZERS[item_type]
    except KeyError as exc:
        raise serializers.ValidationError({"type": "Unknown mechanic content type."}) from exc
    return serializer_class(*args, **kwargs)
