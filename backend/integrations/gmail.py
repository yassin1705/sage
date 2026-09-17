from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.config import GmailConfig


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    provider_message_id: str
    mode: str


class GmailSender:
    def __init__(self, config: GmailConfig) -> None:
        self.config = config

    def send(self, recipient: str, subject: str, body: str) -> DeliveryResult:
        if not self.config.is_live:
            return DeliveryResult(
                status="SIMULATED",
                provider_message_id=f"simulated:{recipient}:{subject}",
                mode="simulation",
            )

        if not self.config.token_file.exists():
            raise RuntimeError(
                "Gmail token is missing. Run: python -m backend.integrations.gmail_auth"
            )

        credentials = Credentials.from_authorized_user_file(
            self.config.token_file,
            [GMAIL_SEND_SCOPE],
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.config.token_file.write_text(credentials.to_json(), encoding="utf-8")
        if not credentials.valid:
            raise RuntimeError("Gmail credentials are invalid or expired")

        message = EmailMessage()
        message["To"] = recipient
        message["From"] = self.config.sender_name
        message["Subject"] = subject
        message.set_content(body)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        result = service.users().messages().send(
            userId="me",
            body={"raw": encoded},
        ).execute()
        return DeliveryResult(
            status="SENT",
            provider_message_id=result["id"],
            mode="gmail_api",
        )
