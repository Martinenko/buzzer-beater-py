import smtplib
import logging
from email.message import EmailMessage
from typing import Optional
import time

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.settings = get_settings()
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    def is_configured(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_from_email
        )

    def send_email(self, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> None:
        if not self.is_configured():
            raise RuntimeError("SMTP is not configured")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from_email
        message["To"] = to_email
        message.set_content(text_body)

        if html_body:
            message.add_alternative(html_body, subtype="html")

        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Use port 587 for TLS (more compatible with cloud platforms)
                # Fallback to 465 with SSL if port is explicitly 465
                if self.settings.smtp_port == 587 or self.settings.smtp_use_tls:
                    # TLS connection (port 587 recommended for cloud)
                    with smtplib.SMTP(
                        self.settings.smtp_host,
                        self.settings.smtp_port or 587,
                        timeout=30
                    ) as server:
                        server.starttls()
                        if self.settings.smtp_username:
                            server.login(self.settings.smtp_username, self.settings.smtp_password)
                        server.send_message(message)
                        logger.info(f"✅ Email sent to {to_email}")
                        return
                else:
                    # SSL connection (port 465)
                    with smtplib.SMTP_SSL(
                        self.settings.smtp_host,
                        self.settings.smtp_port or 465,
                        timeout=30
                    ) as server:
                        if self.settings.smtp_username:
                            server.login(self.settings.smtp_username, self.settings.smtp_password)
                        server.send_message(message)
                        logger.info(f"✅ Email sent to {to_email}")
                        return
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Email send attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                break

        # If we get here, all retries failed
        error_msg = f"Failed to send email after {self.max_retries} attempts: {str(last_error)}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)


email_service = EmailService()

