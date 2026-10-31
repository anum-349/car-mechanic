from rest_framework import serializers

from diagnosis.models import DiagnosisSession
from knowledge.models import Cause

from .models import ScamCheck


class ScamCheckCreateSerializer(serializers.Serializer):
    session = serializers.PrimaryKeyRelatedField(
        queryset=DiagnosisSession.objects.all())
    claimed_cause = serializers.PrimaryKeyRelatedField(
        queryset=Cause.objects.visible(), required=False, allow_null=True)
    claim_text = serializers.CharField(max_length=300, required=False, allow_blank=True)
    quoted_price = serializers.IntegerField(min_value=1, max_value=100_000_000)
    city = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("claimed_cause") and not attrs.get("claim_text", "").strip():
            raise serializers.ValidationError({
                "claim_text": "Choose a cause or enter the mechanic's claim."})
        attrs["claim_text"] = attrs.get("claim_text", "").strip()
        return attrs


class ScamCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScamCheck
        fields = ["id", "user", "session", "claimed_cause", "claim_text",
                  "quoted_price", "plausibility", "verdict", "city",
                  "price_basis", "cost", "reasons", "proof_suggestions",
                  "candidate_causes", "limited", "created_at"]
        read_only_fields = fields
