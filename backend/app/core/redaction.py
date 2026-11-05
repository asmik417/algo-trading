"""Masks configured secrets (APP_PASSWORD, SECRET_KEY, ANTHROPIC_API_KEY) in any text before it leaves the app.
Used for stored error messages and, via a log-record factory, for every log line and traceback.
"""
import logging

MASK = "***"
MIN_SECRET_LEN = 4  # shorter values would mask ordinary words; .env.example asks for long secrets anyway


def _secret_values() -> list[str]:
    """Read at call time, so a changed .env value or a test monkeypatch is always honoured."""
    from app.core.config import settings
    from app.engine import config as engine_config

    values = [settings.APP_PASSWORD, settings.SECRET_KEY, engine_config.ANTHROPIC_API_KEY]
    return sorted({v for v in values if v and len(v) >= MIN_SECRET_LEN}, key=len, reverse=True)


def redact(text: str | None) -> str | None:
    if not text:
        return text
    for value in _secret_values():
        text = text.replace(value, MASK)
    return text


_installed = False


def install_log_redaction() -> None:
    """Wrap the LogRecord factory so every record (message, args and traceback) is redacted at creation,
    whichever handler later writes it."""
    global _installed
    if _installed:
        return
    base_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs) -> logging.LogRecord:
        record = base_factory(*args, **kwargs)
        try:
            message = record.getMessage()
        except Exception:  # malformed %-args: leave the record as is
            return record
        record.msg, record.args = redact(message), ()
        if record.exc_info:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
        return record

    logging.setLogRecordFactory(factory)
    _installed = True
