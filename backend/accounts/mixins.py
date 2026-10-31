from rest_framework.exceptions import ValidationError


class ParamFilterMixin:
    """Filter by simple query params: filter_params = {"param": "orm__lookup"}."""
    filter_params = {}

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        for param, lookup in self.filter_params.items():
            value = self.request.query_params.get(param)
            if value in (None, ""):
                continue
            try:
                queryset = queryset.filter(**{lookup: value})
            except (ValueError, TypeError):
                raise ValidationError({param: "Invalid value."})
        return queryset
