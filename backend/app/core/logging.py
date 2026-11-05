"""One logging setup for the whole backend (console + logs/trade_assistant.log), with secrets masked.
Reuses the engine's logger configuration so API, jobs and engine write to the same place.
"""
from app.core.redaction import install_log_redaction
from app.engine.utils.logger import get_logger

install_log_redaction()

__all__ = ["get_logger"]
