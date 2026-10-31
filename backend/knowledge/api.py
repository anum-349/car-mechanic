"""Shared response metadata for APIs that can return sample knowledge."""


def contains_draft_content(value):
    if isinstance(value, dict):
        if (value.get("is_dummy") is True or value.get("draft_content") is True
                or value.get("status") == "ai_draft"):
            return True
        return any(contains_draft_content(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_draft_content(item) for item in value)
    return False


class DraftContentResponseMixin:
    """Adds a top-level banner flag to successful object-shaped responses."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if (hasattr(response, "data") and isinstance(response.data, dict)
                and response.status_code < 400):
            payload = dict(response.data)
            payload["draft_content"] = contains_draft_content(payload)
            response.data = payload
        return response
