from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    work_quality = serializers.IntegerField(min_value=1, max_value=5, required=False,
                                             allow_null=True)
    price_fairness = serializers.IntegerField(min_value=1, max_value=5, required=False,
                                              allow_null=True)
    communication = serializers.IntegerField(min_value=1, max_value=5, required=False,
                                              allow_null=True)
    timeliness = serializers.IntegerField(min_value=1, max_value=5, required=False,
                                          allow_null=True)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)

    class Meta:
        model = Review
        fields = ["id", "mechanic", "rating", "work_quality", "price_fairness",
                  "communication", "timeliness", "comment", "status",
                  "reviewer_name", "created_at"]
        read_only_fields = ["status", "created_at"]

    @extend_schema_field(serializers.CharField())
    def get_reviewer_name(self, obj):
        return obj.user.name or obj.user.username

    def validate(self, attrs):
        request = self.context["request"]
        mechanic = attrs.get("mechanic") or getattr(self.instance, "mechanic", None)
        if mechanic and mechanic.user_id == request.user.id:
            raise serializers.ValidationError("You cannot review yourself.")
        if self.instance is None:
            if Review.objects.filter(user=request.user, mechanic=mechanic).exists():
                raise serializers.ValidationError(
                    "You have already reviewed this mechanic.")
        elif "mechanic" in attrs and attrs["mechanic"] != self.instance.mechanic:
            raise serializers.ValidationError(
                {"mechanic": "Cannot be changed. Delete and write a new review."})
        criteria = ("work_quality", "price_fairness", "communication", "timeliness")
        supplied_criteria = {key for key in criteria if key in attrs}
        if (self.instance and not supplied_criteria and "rating" in attrs
                and any(getattr(self.instance, key) is not None for key in criteria)):
            raise serializers.ValidationError({
                key: "Update all four review criteria together." for key in criteria
            })
        if supplied_criteria and supplied_criteria != set(criteria):
            raise serializers.ValidationError({
                key: "Rate all four review criteria." for key in criteria
                if key not in supplied_criteria
            })
        if supplied_criteria:
            values = [attrs[key] for key in criteria]
            if any(value is None for value in values):
                raise serializers.ValidationError({
                    key: "A score from 1 to 5 is required." for key in criteria
                    if attrs[key] is None
                })
            attrs["rating"] = (sum(values) + 2) // 4
        return attrs
