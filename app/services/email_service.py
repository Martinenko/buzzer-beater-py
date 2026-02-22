import smtplib
from email.message import EmailMessage
from typing import Optional

from app.config import get_settings


class EmailService:
    def __init__(self):
        self.settings = get_settings()

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

        # Use SMTP_SSL for port 465 (implicit SSL), SMTP with starttls for port 587 (TLS)
        if self.settings.smtp_port == 465:
            with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as server:
                if self.settings.smtp_username:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()

                if self.settings.smtp_username:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)

                server.send_message(message)


email_service = EmailService()
