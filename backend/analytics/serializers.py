from rest_framework import serializers

from diagnosis.models import DiagnosisSession
from .models import Event


CLIENT_EVENT_NAMES = {
    "session_started", "question_answered", "result_viewed", "share_clicked",
    "outcome_submitted", "scam_check_run",
}
ALLOWED_PROP_KEYS = {"question_id", "category_id", "rank", "share_target", "source"}
ALLOWED_PROP_VALUES = {"native", "download", "copy", "web", "unknown"}


class EventCreateSerializer(serializers.Serializer):
    name = serializers.ChoiceField(choices=sorted(CLIENT_EVENT_NAMES))
    session_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    props = serializers.DictField(required=False, default=dict)

    def validate_props(self, props):
        if len(props) > 8:
            raise serializers.ValidationError("Too many properties.")
        unknown = set(props) - ALLOWED_PROP_KEYS
        if unknown:
            raise serializers.ValidationError("Unsupported or privacy-sensitive properties.")
        for key, value in props.items():
            if key in {"question_id", "category_id", "rank"}:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise serializers.ValidationError({key: "Must be a non-negative integer."})
            elif not isinstance(value, str) or value not in ALLOWED_PROP_VALUES:
                raise serializers.ValidationError({key: "Unsupported value."})
        return props

    def validate_session_id(self, value):
        if value is None:
            return value
        try:
            return DiagnosisSession.objects.get(pk=value, user=self.context["request"].user)
        except DiagnosisSession.DoesNotExist as exc:
            raise serializers.ValidationError("Session not found.") from exc

    def create(self, validated_data):
        session = validated_data.pop("session_id", None)
        return Event.objects.create(user=self.context["request"].user,
                                    session=session, **validated_data)
