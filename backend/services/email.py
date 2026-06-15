"""Email service abstraction.

Wraps Resend (https://resend.com) when `RESEND_API_KEY` is set, falls back to
logging the email body to stdout when it isn't (dev mode). All routes that
need to send transactional emails go through `send_email()` — they never
import the Resend SDK directly.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _resend_configured() -> bool:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    return bool(key) and not key.startswith("xxxx")


def email_provider_status() -> dict:
    """Returns a small JSON-friendly status used by the admin debug endpoint."""
    return {
        "configured": _resend_configured(),
        "provider": "resend" if _resend_configured() else "console",
        "from": os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
    }


async def send_email(
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
) -> dict:
    """Send a transactional email.

    Returns a dict with `{provider, ok, id?, error?}`. Never raises on
    provider failure — callers should still create the token in DB so the
    user can retry via the admin debug endpoint or after configuring Resend.
    """
    if not _resend_configured():
        # Dev fallback — log so the developer can copy the link from supervisor.
        logger.info("---- EMAIL (console fallback) ----")
        logger.info(f"to: {to}")
        logger.info(f"subject: {subject}")
        logger.info(f"html: {html}")
        if text:
            logger.info(f"text: {text}")
        logger.info("---- END EMAIL ----")
        return {"provider": "console", "ok": True}

    # Resend path — lazy import so the SDK isn't required in dev.
    try:
        import resend  # type: ignore
    except ImportError:
        logger.error("resend package not installed but RESEND_API_KEY is set")
        return {"provider": "resend", "ok": False, "error": "sdk_not_installed"}

    resend.api_key = os.environ["RESEND_API_KEY"]
    sender = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    try:
        result = resend.Emails.send({
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
            **({"text": text} if text else {}),
        })
        return {"provider": "resend", "ok": True, "id": result.get("id")}
    except Exception as e:
        logger.error(f"Resend send failed: {e}")
        return {"provider": "resend", "ok": False, "error": str(e)}
