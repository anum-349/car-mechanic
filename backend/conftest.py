import pytest


@pytest.fixture(autouse=True)
def celery_tasks_run_eagerly(settings):
    """Keep task scheduling deterministic and broker-free in the test suite."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.SECURE_SSL_REDIRECT = False
    # Tests intentionally construct draft knowledge records; deployment checks
    # exercise the production profile explicitly with DEBUG=False.
    settings.DEBUG = True
    settings.ALLOW_DRAFT_CONTENT = True
