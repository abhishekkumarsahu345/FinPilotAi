"""
Per-organization SMTP abstraction.

Usage in Celery tasks:
    from reminders.email_sender import send_via_org_smtp

    send_via_org_smtp(
        org=org,
        to=[customer.email],
        subject="...",
        text_body="...",
        html_body="...",   # optional
    )

Falls back to Django's configured global SMTP when:
  - no OrgEmailConfig row exists for the org, or
  - OrgEmailConfig.enabled is False, or
  - smtp_host is blank.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from django.conf import settings as dj_settings

logger = logging.getLogger(__name__)


def _get_from_address(config) -> str:
    """Build 'Name <email>' or plain email string from an OrgEmailConfig."""
    email = config.from_email or dj_settings.EMAIL_FROM
    name = config.from_name.strip()
    if name:
        return f"{name} <{email}>"
    return email


def send_via_org_smtp(
    org,
    to: List[str],
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> None:
    """
    Send an email using the org's custom SMTP config (if enabled and complete),
    otherwise falling back to Django's global email backend.

    Raises smtplib.SMTPException (or subclass) on delivery failure — callers
    should handle retries.

    Password is decrypted in memory only for the duration of the SMTP session
    and never logged.
    """
    try:
        from reminders.models import OrgEmailConfig
        config = OrgEmailConfig.objects.get(organization=org)
        use_custom = config.enabled and bool(config.smtp_host)
    except Exception:
        use_custom = False
        config = None

    if use_custom:
        _send_custom_smtp(config, to, subject, text_body, html_body)
    else:
        _send_django_backend(org, config, to, subject, text_body, html_body)


def _send_custom_smtp(config, to, subject, text_body, html_body):
    """Send through the org's own SMTP server using smtplib directly."""
    from reminders.models import OrgEmailConfig

    password = config.get_password()  # Fernet-decrypted, never logged
    from_addr = _get_from_address(config)
    reply_to = config.reply_to or config.from_email or dj_settings.EMAIL_FROM

    # Build MIME message
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text_body or "", "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg = MIMEText(text_body or "", "plain", "utf-8")

    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    if reply_to != from_addr:
        msg["Reply-To"] = reply_to

    security = config.security
    port = config.smtp_port

    try:
        if security == OrgEmailConfig.Security.SSL:
            server = smtplib.SMTP_SSL(config.smtp_host, port, timeout=15)
        else:
            server = smtplib.SMTP(config.smtp_host, port, timeout=15)
            if security == OrgEmailConfig.Security.TLS:
                server.ehlo()
                server.starttls()
                server.ehlo()

        if config.username and password:
            server.login(config.username, password)

        server.sendmail(from_addr, to, msg.as_string())
        server.quit()
        logger.info(
            "Custom SMTP: sent '%s' to %s via %s:%s",
            subject, to, config.smtp_host, port,
        )
    except Exception:
        logger.exception(
            "Custom SMTP failed for org %s (host=%s port=%s security=%s user=%s). "
            "Password not logged.",
            config.organization_id, config.smtp_host, port, security, config.username,
        )
        raise


def _send_django_backend(org, config, to, subject, text_body, html_body):
    """Fall back to Django's configured email backend (console / SMTP from settings)."""
    from django.core.mail import send_mail

    # Determine from_email: prefer org config from_email if present
    if config and config.from_email:
        from_email = _get_from_address(config)
    else:
        from_email = dj_settings.EMAIL_FROM

    send_mail(
        subject=subject,
        message=text_body or "",
        from_email=from_email,
        recipient_list=to,
        html_message=html_body or None,
        fail_silently=False,
    )
    logger.info("Django backend: sent '%s' to %s", subject, to)


def test_smtp_connection(config) -> dict:
    """
    Attempt to open an SMTP connection and return {ok: bool, message: str}.
    Does NOT send any email.
    """
    from reminders.models import OrgEmailConfig
    try:
        if not config.smtp_host:
            return {"ok": False, "message": "SMTP host is not set."}

        password = config.get_password()
        security = config.security
        port = config.smtp_port

        if security == OrgEmailConfig.Security.SSL:
            server = smtplib.SMTP_SSL(config.smtp_host, port, timeout=10)
        else:
            server = smtplib.SMTP(config.smtp_host, port, timeout=10)
            if security == OrgEmailConfig.Security.TLS:
                server.ehlo()
                server.starttls()
                server.ehlo()

        if config.username and password:
            server.login(config.username, password)

        server.quit()
        return {"ok": True, "message": f"Connected to {config.smtp_host}:{port} successfully."}

    except smtplib.SMTPAuthenticationError:
        return {"ok": False, "message": "Authentication failed. Check username and password."}
    except smtplib.SMTPConnectError as exc:
        return {"ok": False, "message": f"Could not connect to {config.smtp_host}:{config.smtp_port}. {exc}"}
    except TimeoutError:
        return {
            "ok": False,
            "message": f"Connection timed out. Check host, port, and firewall settings.",
        }
    except Exception as exc:
        # Do not include password in the message
        safe_msg = str(exc)
        if config.has_password():
            try:
                plain = config.get_password()
                safe_msg = safe_msg.replace(plain, "***")
            except Exception:
                pass
        return {"ok": False, "message": f"Connection error: {safe_msg}"}
