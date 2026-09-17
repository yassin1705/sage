from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from backend.config import load_gmail_config
from backend.integrations.gmail import GMAIL_SEND_SCOPE


def main() -> None:
    config = load_gmail_config()
    if not config.credentials_file.exists():
        raise SystemExit(
            f"OAuth credentials not found: {config.credentials_file}\n"
            "Download the desktop OAuth client JSON from Google Cloud and place it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        config.credentials_file,
        [GMAIL_SEND_SCOPE],
    )
    credentials = flow.run_local_server(port=0)
    config.token_file.parent.mkdir(parents=True, exist_ok=True)
    config.token_file.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Gmail authorization saved to {config.token_file}")


if __name__ == "__main__":
    main()
