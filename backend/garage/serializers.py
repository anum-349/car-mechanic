from datetime import date

from rest_framework import serializers

from .models import Car, CarMake, CarModel, ServiceLog


class CarMakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarMake
        fields = ["id", "name"]


class CarModelSerializer(serializers.ModelSerializer):
    make_name = serializers.CharField(source="car_make.name", read_only=True)
    label = serializers.CharField(source="__str__", read_only=True)
    year_from = serializers.IntegerField(min_value=1980, max_value=date.today().year + 1)
    year_to = serializers.IntegerField(
        min_value=1980, max_value=date.today().year + 1, required=False,
        allow_null=True,
    )
    engine_cc = serializers.IntegerField(min_value=0, max_value=20_000,
                                         required=False, allow_null=True)

    class Meta:
        model = CarModel
        fields = ["id", "car_make", "make_name", "name", "generation",
                  "year_from", "year_to", "engine_cc", "fuel_type", "label"]


class CarSerializer(serializers.ModelSerializer):
    car_model_label = serializers.CharField(source="car_model.__str__",
                                            read_only=True)
    year = serializers.IntegerField(min_value=1980, max_value=date.today().year + 1,
                                    required=False)
    mileage_km = serializers.IntegerField(min_value=0, max_value=2_000_000,
                                          required=False)

    class Meta:
        model = Car
        fields = ["id", "car_model", "car_model_label", "nickname", "year",
                  "mileage_km", "transmission", "fuel_type"]

    def validate(self, attrs):
        model = attrs.get("car_model") or getattr(self.instance, "car_model", None)
        year = attrs.get("year") or getattr(self.instance, "year", None)
        if model and year:
            if year < model.year_from or (model.year_to and year > model.year_to):
                end = model.year_to or "now"
                raise serializers.ValidationError(
                    {"year": f"{model} was made {model.year_from} to {end}."})
        return attrs


class ServiceLogSerializer(serializers.ModelSerializer):
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    mileage_km = serializers.IntegerField(min_value=0, max_value=2_000_000,
                                          required=False, allow_null=True)
    cost = serializers.IntegerField(min_value=0, max_value=100_000_000,
                                    required=False, allow_null=True)

    class Meta:
        model = ServiceLog
        fields = ["id", "car", "service_type", "service_date", "mileage_km",
                  "cost", "next_due_date", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:  # only my own cars
            self.fields["car"].queryset = Car.objects.filter(user=request.user)

    def validate(self, attrs):
        date = attrs.get("service_date") or getattr(self.instance, "service_date", None)
        due = attrs.get("next_due_date")
        if date and due and due < date:
            raise serializers.ValidationError(
                {"next_due_date": "Cannot be before the service date."})
        return attrs
