from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def require_private_admin_url(app_configs, **kwargs):
    if not settings.DEBUG and settings.ADMIN_URL.strip("/").lower() == "admin":
        return [Error(
            "Set ADMIN_URL to a private, randomly generated path in production.",
            id="security.E001",
        )]
    return []
