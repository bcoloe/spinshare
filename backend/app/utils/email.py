# backend/app/utils/email.py

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import resend

from app.config import get_settings

logger = logging.getLogger(__name__)


# ==================== RESEND PROVIDER ====================


def _send_via_resend(*, to_email: str, subject: str, plain: str, html: str) -> None:
    """Deliver a single email through the Resend API."""
    settings = get_settings()
    resend.api_key = settings.RESEND_API_KEY

    resend.Emails.send(
        {
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "text": plain,
            "html": html,
        }
    )


# ==================== SMTP PROVIDER ====================


def _send_via_smtp(*, to_email: str, subject: str, plain: str, html: str) -> None:
    """Deliver a single email through a standard SMTP server."""
    settings = get_settings()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())


# ==================== DISPATCHER ====================


def _send_email(*, to_email: str, subject: str, plain: str, html: str) -> None:
    """Route to the configured email provider (resend or smtp).

    Logs and swallows all delivery failures so callers are never blocked by
    a transient email error — DB records (invites, reset tokens) remain valid.
    """
    settings = get_settings()

    if not settings.SMTP_ENABLED:
        logger.info(
            "Email disabled — skipping '%s' to %s", subject, to_email
        )
        return

    provider = settings.EMAIL_PROVIDER.lower()
    try:
        if provider == "resend":
            _send_via_resend(to_email=to_email, subject=subject, plain=plain, html=html)
        elif provider == "smtp":
            _send_via_smtp(to_email=to_email, subject=subject, plain=plain, html=html)
        else:
            logger.error("Unknown EMAIL_PROVIDER '%s' — email not sent to %s", provider, to_email)
    except Exception:
        logger.exception("Failed to send '%s' to %s via %s", subject, to_email, provider)


# ==================== PUBLIC API ====================


def send_invitation_email(
    *,
    to_email: str,
    group_name: str,
    inviter_username: str,
    invite_url: str,
) -> None:
    """Send a group invitation email.

    No-ops when SMTP_ENABLED is False (default in dev/test).
    Logs and swallows all delivery failures — the invitation DB record is
    already committed at call time, so the invite link remains valid even
    when the email cannot be delivered.
    """
    settings = get_settings()
    if not settings.SMTP_ENABLED:
        logger.info("Email disabled — skipping invitation email to %s (url=%s)", to_email, invite_url)
        return

    subject = f"You've been invited to join {group_name} on SpinShare"

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

    _send_email(to_email=to_email, subject=subject, plain=plain, html=html)


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    """Send a password reset email containing a one-time reset link.

    No-ops when SMTP_ENABLED is False (default in dev/test) — logs the URL
    instead so developers can test the flow without live email.
    Logs and swallows delivery failures; the token remains valid regardless.
    """
    settings = get_settings()
    if not settings.SMTP_ENABLED:
        logger.warning(
            "Email disabled — skipping password reset email to %s (url=%s)", to_email, reset_url
        )
        return

    subject = "Reset your SpinShare password"

    plain = (
        f"You requested a password reset for your SpinShare account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in 30 minutes. If you did not request a reset, "
        f"you can safely ignore this email.\n"
    )

    html = f"""\
<html><body>
  <p>You requested a password reset for your SpinShare account.</p>
  <p><a href="{reset_url}">Reset your password</a></p>
  <p>This link expires in <strong>30 minutes</strong>. If you did not request
     a reset, you can safely ignore this email.</p>
</body></html>"""

    _send_email(to_email=to_email, subject=subject, plain=plain, html=html)
