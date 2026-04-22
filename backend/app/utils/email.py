# backend/app/utils/email.py

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_invitation_email(
    *,
    to_email: str,
    group_name: str,
    inviter_username: str,
    invite_url: str,
) -> None:
    """Send a group invitation email.

    No-ops when SMTP_ENABLED is False (default in dev/test).
    Raises smtplib.SMTPException on delivery failure.
    """
    settings = get_settings()

    if not settings.SMTP_ENABLED:
        logger.info("SMTP disabled — skipping invitation email to %s (url=%s)", to_email, invite_url)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"You've been invited to join {group_name} on SpinShare"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email

    plain = (
        f"{inviter_username} has invited you to join '{group_name}' on SpinShare.\n\n"
        f"Accept the invitation: {invite_url}\n\n"
        f"This link expires in 7 days. If you don't have an account yet, register at "
        f"{settings.FRONTEND_URL}/register and then use the link above.\n"
    )

    html = f"""\
<html><body>
  <p><strong>{inviter_username}</strong> has invited you to join
     <strong>{group_name}</strong> on SpinShare.</p>
  <p><a href="{invite_url}">Accept invitation</a></p>
  <p>This link expires in 7 days. If you don't have an account yet,
     <a href="{settings.FRONTEND_URL}/register">register here</a>
     and then click the invite link above.</p>
</body></html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())
    except smtplib.SMTPException:
        logger.exception("Failed to send invitation email to %s", to_email)
        raise
