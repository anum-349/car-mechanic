"""External reminder channel stubs, enabled explicitly by settings."""
import logging

logger = logging.getLogger(__name__)


def send_push_reminder(user, session_id):
    logger.info("Push reminder adapter is not configured for user %s", user.pk)


def send_whatsapp_reminder(user, session_id):
    logger.info("WhatsApp reminder adapter is not configured for user %s", user.pk)


def dispatch_outcome_reminder(session):
    send_push_reminder(session.user, session.pk)
    send_whatsapp_reminder(session.user, session.pk)
