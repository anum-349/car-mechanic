import re

from rest_framework import serializers

from diagnosis.models import (
    DiagnosisSession, MechanicInspection, MechanicOutcomeAudit,
    MechanicRepairOutcome, SessionAnswer, SessionResult,
)
from garage.models import Car


class MechanicCarSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="__str__", read_only=True)
    model = serializers.CharField(source="car_model.__str__", read_only=True)

    class Meta:
        model = Car
        fields = ["id", "label", "model", "year", "mileage_km"]


class SessionAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text_en", read_only=True)
    answer_text = serializers.CharField(source="option.label", read_only=True)

    class Meta:
        model = SessionAnswer
        fields = ["id", "question", "question_text", "option", "answer_text",
                  "free_text", "answered_at"]


class SessionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionResult
        fields = ["cause", "cause_name", "rank", "confidence", "explanation"]


class MechanicInspectionSerializer(serializers.ModelSerializer):
    mechanic = serializers.PrimaryKeyRelatedField(read_only=True)
    mechanic_name = serializers.CharField(source="mechanic.username", read_only=True)
    suspected_cause_name = serializers.CharField(
        source="suspected_cause.name", read_only=True)

    class Meta:
        model = MechanicInspection
        fields = [
            "id", "mechanic", "mechanic_name", "inspection_date", "mileage_km", "findings",
            "tests_performed", "tools_used", "additional_obd_codes",
            "suspected_cause", "suspected_cause_name", "suspected_cause_text",
            "safety_concerns",
            "further_testing_required", "status", "submitted_at", "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mechanic", "mechanic_name", "status", "submitted_at",
                            "created_at", "updated_at"]

    def validate_additional_obd_codes(self, value):
        if not isinstance(value, list) or len(value) > 20:
            raise serializers.ValidationError("Provide a list of at most 20 OBD codes.")
        if any(not isinstance(code, str) or not re.fullmatch(
                r"[A-Z][0-9A-F][0-9A-F0-9]{3}", code.strip().upper())
               for code in value):
            raise serializers.ValidationError("Each entry must be a valid OBD code.")
        return list(dict.fromkeys(code.strip().upper() for code in value))

    def validate(self, attrs):
        cause = attrs.get("suspected_cause",
                          getattr(self.instance, "suspected_cause", None))
        cause_text = attrs.get("suspected_cause_text",
                               getattr(self.instance, "suspected_cause_text", ""))
        if cause and cause_text:
            raise serializers.ValidationError({
                "suspected_cause_text": "Choose a listed cause or enter a cause description."
            })
        return attrs


class MechanicOutcomeSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(source="mechanic.username", read_only=True)
    actual_cause_name = serializers.CharField(
        source="actual_cause.name", read_only=True)

    class Meta:
        model = MechanicRepairOutcome
        fields = [
            "id", "actual_cause", "actual_cause_name", "actual_cause_text",
            "actual_cost", "mechanic",
            "mechanic_name", "notes", "repair_status",
            "result_status", "repair_actions", "parts_replaced", "follow_up_notes",
            "parts_cost", "labor_cost", "other_cost", "repaired_at", "created_at",
            "submitted_at",
        ]
        read_only_fields = ["id", "mechanic", "mechanic_name", "created_at",
                            "submitted_at"]

    def validate(self, attrs):
        for field in ("actual_cost", "parts_cost", "labor_cost", "other_cost"):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value is not None and value > 100_000_000:
                raise serializers.ValidationError({field: "Cost cannot exceed 100,000,000 PKR."})
        cause = attrs.get("actual_cause", getattr(self.instance, "actual_cause", None))
        cause_text = attrs.get("actual_cause_text",
                               getattr(self.instance, "actual_cause_text", ""))
        if cause and cause_text:
            raise serializers.ValidationError({
                "actual_cause_text": "Choose a listed cause or enter a cause description."
            })
        component_fields = ("parts_cost", "labor_cost", "other_cost")
        if any(field in attrs for field in component_fields):
            components = [
                attrs.get(field, getattr(self.instance, field, None))
                for field in component_fields
            ]
            if any(value is not None for value in components):
                total = sum(value or 0 for value in components)
                if total > 100_000_000:
                    raise serializers.ValidationError({
                        "actual_cost": "Combined costs cannot exceed 100,000,000 PKR."
                    })
                attrs["actual_cost"] = total
        return attrs


class MechanicOutcomeAuditSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(source="mechanic.username", read_only=True)

    class Meta:
        model = MechanicOutcomeAudit
        fields = ["id", "mechanic_name", "action", "snapshot", "created_at"]


class MechanicRecordSerializer(serializers.ModelSerializer):
    car = MechanicCarSerializer(read_only=True)
    category_label = serializers.CharField(source="category.name_en", read_only=True)
    answers = SessionAnswerSerializer(many=True, read_only=True)
    results = SessionResultSerializer(many=True, read_only=True)
    symptoms = serializers.SerializerMethodField()
    inspections = MechanicInspectionSerializer(
        source="mechanic_inspections", many=True, read_only=True)
    outcome = MechanicOutcomeSerializer(
        source="mechanic_outcome", read_only=True)
    outcome_history = serializers.SerializerMethodField()
    obd_context = serializers.SerializerMethodField()

    class Meta:
        model = DiagnosisSession
        fields = ["id", "status", "diagnosis_type", "free_text", "car", "category_label",
                  "obd_code", "obd_context", "safety_alert", "started_at",
                  "completed_at", "symptoms", "answers", "results", "inspections",
                  "outcome", "outcome_history"]

    def get_symptoms(self, session):
        return [{
            "id": item.symptom_id,
            "text": item.symptom.text_en,
            "source": item.source,
        } for item in session.session_symptoms.all()]

    def get_obd_context(self, session):
        code = session.obd_code
        if not code:
            return None
        return {"code": code.code, "description": code.description,
                "system": code.system}

    def get_outcome_history(self, session):
        if not hasattr(session, "mechanic_outcome"):
            return []
        audit = session.mechanic_outcome.audit_entries.all()
        return MechanicOutcomeAuditSerializer(audit, many=True).data
