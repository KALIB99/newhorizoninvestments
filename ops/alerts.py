"""Alerting + logging setup. Telegram if configured, loguru always. Messages are plain text;
nothing from Settings is ever interpolated into them."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from ops.settings import get_settings


def setup_logging(logs_dir: Path | None = None, level: str = "INFO") -> None:
    s = get_settings()
    d = logs_dir or s.logs_dir
    d.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=level)
    logger.add(d / "firm_{time:YYYY-MM-DD}.log", rotation="00:00", retention="90 days", level="DEBUG", enqueue=True)


def alert(text: str, level: str = "WARNING") -> bool:
    """Send to Telegram if configured. Returns whether a remote alert was sent."""
    logger.log(level, "ALERT: {}", text)
    s = get_settings()
    if not (s.telegram_bot_token and s.telegram_chat_id):
        return False
    try:
        import urllib.parse
        import urllib.request

        url = f"https://api.telegram.org/bot{s.telegram_bot_token.get_secret_value()}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": s.telegram_chat_id, "text": text[:4000]}).encode()
        with urllib.request.urlopen(url, data=data, timeout=10) as r:  # noqa: S310 - https, fixed host
            return r.status == 200
    except Exception as e:  # noqa: BLE001
        logger.error("telegram alert failed: {}", type(e).__name__)
        return False
