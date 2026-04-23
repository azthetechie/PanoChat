"""Email delivery via Resend (optional — falls back to stdout log)."""
import os
import asyncio
import logging

import resend

logger = logging.getLogger("email_service")

# Addresses/domains that don't need verification (Resend test sender)
ALLOWED_DOMAINS_WITHOUT_VERIFY = {"resend.dev"}


def _configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY"))


def _init() -> None:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if key:
        resend.api_key = key


def _from_header() -> str:
    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev").strip()
    name = os.environ.get("EMAIL_FROM_NAME", "Panorama Comms").strip()
    if name:
        return f"{name} <{sender}>"
    return sender


def _sender_domain() -> str:
    sender = os.environ.get("SENDER_EMAIL", "").strip()
    if "@" in sender:
        return sender.split("@", 1)[1].lower()
    return ""


def validate_sender_domain() -> dict:
    """Check Resend for verified domains and warn if SENDER_EMAIL's domain isn't one.

    Returns {configured, sender, domain, verified, warning, domains} — never raises.
    Called once on startup; logs a clear warning for admins if misconfigured.
    """
    sender = os.environ.get("SENDER_EMAIL", "").strip()
    domain = _sender_domain()
    result = {
        "configured": _configured(),
        "sender": sender,
        "domain": domain,
        "verified": False,
        "warning": None,
        "domains": [],
    }

    if not _configured():
        result["warning"] = "RESEND_API_KEY is empty — password-reset emails will fall back to stdout logs."
        logger.warning(result["warning"])
        return result

    if not sender:
        result["warning"] = "SENDER_EMAIL is empty — Resend sends will fail. Set SENDER_EMAIL in .env."
        logger.warning(result["warning"])
        return result

    if domain in ALLOWED_DOMAINS_WITHOUT_VERIFY:
        result["verified"] = True
        logger.info(
            "Email: using Resend test sender '%s' — delivery restricted to the Resend account owner's "
            "address. For production, verify your own domain at https://resend.com/domains.",
            sender,
        )
        return result

    try:
        _init()
        listed = resend.Domains.list()
        # SDK returns either a dict {"data": [...]} or a list depending on version
        items = listed.get("data") if isinstance(listed, dict) else listed
        verified_domains = []
        for d in items or []:
            name = (d.get("name") or "").lower()
            status = (d.get("status") or "").lower()
            if status == "verified":
                verified_domains.append(name)
        result["domains"] = verified_domains
        if domain in verified_domains:
            result["verified"] = True
            logger.info("Email: SENDER_EMAIL domain '%s' is verified with Resend. ✅", domain)
        else:
            msg = (
                f"Email: SENDER_EMAIL domain '{domain}' is NOT verified with Resend. "
                f"Password-reset emails will fail at send time and fall back to stdout logs. "
                f"Verify the domain at https://resend.com/domains (verified so far: "
                f"{verified_domains or 'none'})."
            )
            result["warning"] = msg
            logger.warning(msg)
    except Exception as e:  # noqa: BLE001
        msg = f"Email: could not verify Resend domains ({e}). Will still attempt sends."
        result["warning"] = msg
        logger.warning(msg)

    return result


async def send_password_reset(
    to_email: str, reset_link: str, brand_name: str = "Panorama Comms"
) -> bool:
    """Send a password-reset email. Returns True on success, False otherwise.
    Never raises — errors are logged."""
    if not _configured():
        logger.info(
            "[PASSWORD_RESET] (email disabled — no RESEND_API_KEY) link for %s: %s",
            to_email,
            reset_link,
        )
        return False

    _init()
    subject = f"Reset your {brand_name} password"
    text = (
        f"Hi,\n\n"
        f"We received a request to reset the password for your {brand_name} account.\n"
        f"Click the link below to set a new password. It expires in 1 hour.\n\n"
        f"{reset_link}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n"
    )
    html = f"""
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#fafafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0a0a0a;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e4e4e7;">
            <tr>
              <td style="padding:32px 32px 8px 32px;border-bottom:1px solid #e4e4e7;">
                <div style="font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:#FF5A00;font-weight:800;">// PASSWORD RESET</div>
                <div style="font-size:24px;font-weight:800;margin-top:6px;letter-spacing:-0.02em;">{brand_name}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px;">
                <p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;">
                  We received a request to reset the password for your account.
                  Click the button below to set a new one. <strong>This link expires in 1 hour.</strong>
                </p>
                <p style="margin:0 0 24px 0;">
                  <a href="{reset_link}" style="display:inline-block;padding:12px 24px;background:#FF5A00;color:#ffffff;text-decoration:none;font-weight:700;letter-spacing:0.02em;">
                    Reset password →
                  </a>
                </p>
                <p style="margin:0;font-size:12px;color:#71717a;line-height:1.6;">
                  Or copy and paste this URL into your browser:<br>
                  <a href="{reset_link}" style="color:#FF5A00;word-break:break-all;">{reset_link}</a>
                </p>
                <p style="margin:24px 0 0 0;font-size:12px;color:#71717a;line-height:1.6;">
                  Didn't request this? You can safely ignore this email.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px;border-top:1px solid #e4e4e7;font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:#71717a;">
                Self-hosted · {brand_name}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()

    params = {
        "from": _from_header(),
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info("Password reset email sent to %s", to_email)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Resend send failed for %s: %s", to_email, e)
        # Always log the reset link as a fallback so admins can recover manually
        logger.info("[PASSWORD_RESET] (fallback) link for %s: %s", to_email, reset_link)
        return False
