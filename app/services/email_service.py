import requests
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.settings = get_settings()
        self.max_retries = 3
        self.retry_delay = 1  # second
        
        # Debug logging
        logger.info(f"📧 Brevo API Key configured: {bool(self.settings.brevo_api_key)}")
        logger.info(f"📧 SMTP From Email configured: {bool(self.settings.smtp_from_email)}")

    def is_configured(self) -> bool:
        configured = bool(
            self.settings.brevo_api_key
            and self.settings.smtp_from_email
        )
        if not configured:
            logger.warning(f"⚠️ Email not configured - API Key: {bool(self.settings.brevo_api_key)}, From Email: {bool(self.settings.smtp_from_email)}")
        return configured

    def send_email(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> None:
        if not self.is_configured():
            raise RuntimeError("Brevo is not configured")

        brevo_api_key = self.settings.brevo_api_key
        from_email = self.settings.smtp_from_email

        # Brevo API endpoint
        url = "https://api.brevo.com/v3/smtp/email"

        # Prepare request headers and body
        headers = {
            "accept": "application/json",
            "api-key": brevo_api_key,
            "content-type": "application/json",
        }

        payload = {
            "sender": {
                "name": "BB Scout",
                "email": from_email
            },
            "to": [
                {
                    "email": to_email
                }
            ],
            "subject": subject,
            "textContent": text_body,
        }

        if html_body:
            payload["htmlContent"] = html_body

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=15
                )

                if response.status_code in [200, 201]:
                    message_id = response.json().get('messageId', 'unknown')
                    logger.info(f"✅ Email sent to {to_email} via Brevo (ID: {message_id})")
                    return
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"⚠️ Brevo API attempt {attempt + 1}/{self.max_retries} failed: {last_error}")
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ Email send attempt {attempt + 1}/{self.max_retries} failed: {last_error}")

            if attempt < self.max_retries - 1:
                import time
                time.sleep(self.retry_delay)

        # All retries failed
        error_msg = f"Failed to send email after {self.max_retries} attempts: {last_error}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)


email_service = EmailService()



