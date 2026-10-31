import logging

from celery import shared_task
from django.conf import settings

from .models import DiagnosisSession, Notification

logger = logging.getLogger(__name__)


@shared_task(name="diagnosis.send_outcome_reminder")
def send_outcome_reminder(session_id):
    session = (DiagnosisSession.objects.select_related("user")
               .filter(pk=session_id, status=DiagnosisSession.Status.COMPLETED).first())
    if session is None or hasattr(session, "outcome"):
        return False
    Notification.objects.get_or_create(
        dedupe_key=f"outcome-reminder:{session.pk}",
        defaults={"user": session.user, "kind": "outcome_reminder",
                  "payload": {"session_id": session.pk}})
    if settings.OUTCOME_REMINDER_EXTERNAL_ENABLED:
        from .services.reminder_channels import dispatch_outcome_reminder
        dispatch_outcome_reminder(session)
    return True
