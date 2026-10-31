from django.conf import settings
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ProjectStaticFilesStorage(ManifestStaticFilesStorage):
    """Use the manifest strictly in production, where collectstatic is required."""

    manifest_strict = not settings.DEBUG
