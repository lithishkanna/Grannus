"""
SMS Gateway Service for Grannus RuralCare AI.
Integrates with:
  - MSG91 (India DLT Compliant SMS & OTP Gateway)
  - Twilio (International / Multi-region fallback)
  - Sandbox / Local Console Gateway (credit-saving dev mode)
"""
import logging
import re
import urllib.parse
import urllib.request
import json
from typing import Tuple, Optional

from app.config import get_settings

logger = logging.getLogger("rural_care.sms")

# Internal development & demo test numbers that bypass external SMS network
# to protect the user's limited tier quota while developing.
SANDBOX_TEST_NUMBERS = {
    "+919876543210",
    "9876543210",
    "+919999999999",
    "9999999999",
}


def normalize_mobile_for_india(phone: str) -> str:
    """Normalize phone number to MSG91 format: country code + 10 digits (e.g., 919876543210)."""
    clean = re.sub(r"[^\d]", "", phone.strip())
    if len(clean) == 10:
        return f"91{clean}"
    if clean.startswith("91") and len(clean) == 12:
        return clean
    if clean.startswith("0") and len(clean) == 11:
        return f"91{clean[1:]}"
    return clean


def send_sms_otp(phone_number: str, otp_code: str) -> Tuple[bool, str]:
    """
    Dispatch single-use 6-digit OTP code to the patient's mobile phone.
    Returns: (success: bool, user_message: str)
    Fails closed: if provider errors, returns (False, error_message).
    """
    settings = get_settings()
    phone_clean = phone_number.strip()
    is_dev = settings.env == "development" or settings.allow_dev_otp

    # 1. Gate sandbox test numbers strictly behind development (preserve quota)
    if is_dev and (phone_clean in SANDBOX_TEST_NUMBERS or phone_clean.replace("+", "") in SANDBOX_TEST_NUMBERS):
        logger.info("Sandbox test number detected (%s) in dev mode. Skipping external SMS.", phone_clean)
        return True, "Sandbox test code active (Code: 123456)."

    provider = (settings.sms_provider or "msg91").lower().strip()

    # 2. Dispatch via MSG91
    if provider == "msg91":
        auth_key = settings.msg91_auth_key
        if not auth_key:
            if is_dev:
                logger.warning("MSG91_AUTH_KEY is not configured. Falling back to local dev mode.")
                return True, "Verification code generated (local sandbox mode)."
            logger.error("SMS Gateway error: MSG91_AUTH_KEY is not configured in %s environment.", settings.env)
            return False, "SMS provider authentication key is not configured."

        mobile = normalize_mobile_for_india(phone_clean)
        template_id = settings.msg91_template_id or ""

        try:
            # MSG91 v5 Send OTP Endpoint
            query_params = {
                "mobile": mobile,
                "authkey": auth_key,
                "otp": otp_code,
                "otp_expiry": "5",
            }
            if template_id:
                query_params["template_id"] = template_id

            encoded_query = urllib.parse.urlencode(query_params)
            url = f"https://control.msg91.com/api/v5/otp?{encoded_query}"

            headers = {
                "authkey": auth_key,
                "Content-Type": "application/json",
                "User-Agent": "Grannus-RuralCare-AI/1.0",
            }

            body_data = json.dumps({"otp": otp_code}).encode("utf-8")
            req = urllib.request.Request(url, data=body_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=8.0) as response:
                status_code = response.getcode()
                response_text = response.read().decode("utf-8")

                try:
                    resp_json = json.loads(response_text)
                except Exception:
                    resp_json = {}

                # MSG91 returns {"message":"...", "type":"success"}
                if status_code in (200, 201) and resp_json.get("type") != "error":
                    logger.info("MSG91 OTP SMS successfully dispatched to %s****%s", mobile[:4], mobile[-2:])
                    return True, "Verification code sent to your mobile phone via SMS."
                else:
                    msg = resp_json.get("message", "Provider returned error status.")
                    logger.error("MSG91 API error for %s: %s", mobile, msg)
                    return False, f"Failed to deliver verification SMS: {msg}"

        except Exception as exc:
            logger.error("Could not reach MSG91 gateway for %s: %s", phone_clean, exc)
            if is_dev:
                logger.info("Development fallback: allowing dev verification code for %s", phone_clean)
                return True, "Verification code generated (dev fallback)."
            return False, "SMS gateway connection failed. Please try again later."

    # 3. Dispatch via Twilio (if configured)
    elif provider == "twilio" and settings.twilio_account_sid and settings.twilio_auth_token:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
            post_data = urllib.parse.urlencode({
                "To": phone_clean if phone_clean.startswith("+") else f"+{phone_clean}",
                "From": settings.twilio_phone_number,
                "Body": f"Your Grannus verification code is {otp_code}. Valid for 5 minutes.",
            }).encode("utf-8")

            import base64
            auth_str = f"{settings.twilio_account_sid}:{settings.twilio_auth_token}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()

            req = urllib.request.Request(
                url,
                data=post_data,
                headers={"Authorization": f"Basic {auth_b64}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8.0) as response:
                if response.getcode() in (200, 201):
                    logger.info("Twilio SMS dispatched successfully to %s", phone_clean)
                    return True, "Verification code sent via SMS."
                else:
                    logger.error("Twilio SMS failed with HTTP status %s", response.getcode())
                    return False, "Twilio SMS dispatch failed."
        except Exception as exc:
            logger.error("Twilio SMS dispatch failed: %s", exc)
            return False, "Twilio gateway connection failed."

    # 4. Local / Console fallback (strictly gated to development)
    if is_dev:
        logger.info("SMS Gateway Console Mode (Dev): OTP for %s is %s", phone_clean, otp_code)
        return True, "Verification code sent to your phone."

    return False, "No active SMS provider configured for production."
