from django.contrib.auth.password_validation import validate_password
from django.db.models import Avg
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from drf_spectacular.utils import extend_schema_field, OpenApiTypes

from .models import MechanicProfile, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8,
                                     style={"input_type": "password"})
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    city = serializers.CharField(max_length=60, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    class Meta:
        model = User
        fields = ["id", "username", "password", "name", "phone", "city", "language"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_phone(self, value):
        return value or None  # many users may have no phone; "" would clash

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(
            password=password, role=User.Role.USER, **validated_data
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "name", "phone", "city",
                  "language", "role"]
        read_only_fields = ["id", "username", "role"]

    def validate_phone(self, value):
        return value or None


class LoginTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class MechanicProfileSerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    class Meta:
        model = MechanicProfile
        fields = ["user", "workshop_name", "address", "city", "phone", "experience_years",
                  "specialization", "is_verified", "honesty_score",
                  "average_rating", "review_count", "created_at", "updated_at"]
        read_only_fields = ["user", "is_verified", "honesty_score"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_phone(self, obj):
        return obj.user.phone

    def _approved(self, obj):
        return obj.reviews.filter(status="approved")

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_average_rating(self, obj):
        avg = self._approved(obj).aggregate(a=Avg("rating"))["a"]
        return round(avg, 1) if avg else None

    @extend_schema_field(serializers.IntegerField())
    def get_review_count(self, obj):
        return self._approved(obj).count()


class MechanicRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    city = serializers.CharField(max_length=60, required=False, allow_blank=True)
    language = serializers.ChoiceField(choices=User.Language.choices, default="en")
    workshop_name = serializers.CharField(max_length=150)
    address = serializers.CharField(max_length=250, required=False, allow_blank=True)
    experience_years = serializers.IntegerField(min_value=0, max_value=80, default=0)
    specialization = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value or None

    def validate_phone(self, value):
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("A user with that phone already exists.")
        return value or None

    def create(self, validated_data):
        profile_fields = {key: validated_data.pop(key) for key in
                          ("workshop_name", "address", "experience_years", "specialization")
                          if key in validated_data}
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, role=User.Role.MECHANIC,
                                        **validated_data)
        profile = MechanicProfile.objects.create(
            user=user, city=user.city, is_verified=False, **profile_fields)
        return {"user": user, "profile": profile}


class MechanicRegistrationResponseSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_user(self, obj):
        user = obj["user"]
        return {"id": user.pk, "username": user.username, "email": user.email,
                "phone": user.phone, "city": user.city, "language": user.language,
                "role": user.role}

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_profile(self, obj):
        profile = obj["profile"]
        return {"workshop_name": profile.workshop_name, "address": profile.address,
                "city": profile.city,
                "experience_years": profile.experience_years,
                "specialization": profile.specialization,
                "is_verified": profile.is_verified}
