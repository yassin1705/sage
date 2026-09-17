from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent / "config"


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class GmailConfig:
    mode: str
    sender_name: str
    credentials_file: Path
    token_file: Path

    @property
    def is_live(self) -> bool:
        return self.mode == "gmail_api"


@dataclass(frozen=True)
class AgentConfig:
    enabled: bool
    base_url: str
    model: str
    timeout_seconds: float
    keep_alive: str


def load_gmail_config() -> GmailConfig:
    data = json.loads((CONFIG_DIR / "gmail.json").read_text(encoding="utf-8"))
    mode = data.get("mode", "simulation")
    if mode not in {"simulation", "gmail_api"}:
        raise ValueError("gmail.mode must be 'simulation' or 'gmail_api'")
    return GmailConfig(
        mode=mode,
        sender_name=data.get("sender_name", "SAGE Service Desk"),
        credentials_file=_resolve_project_path(data["credentials_file"]),
        token_file=_resolve_project_path(data["token_file"]),
    )


def load_agent_config() -> AgentConfig:
    data = json.loads((CONFIG_DIR / "agent.json").read_text(encoding="utf-8"))
    return AgentConfig(
        enabled=bool(data.get("enabled", True)),
        base_url=data.get("base_url", "http://127.0.0.1:11434").rstrip("/"),
        model=data.get("model", "qwen3:8b"),
        timeout_seconds=float(data.get("timeout_seconds", 45)),
        keep_alive=data.get("keep_alive", "30m"),
    )
