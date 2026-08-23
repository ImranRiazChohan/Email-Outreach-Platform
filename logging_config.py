"""Application-wide logging setup. Never logs secrets such as API keys."""
from __future__ import annotations

import logging
import sys

import config

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger, configuring handlers on first use."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(config.LOG_DIR / "app.log", encoding="utf-8"),
            ],
        )
        _CONFIGURED = True
    return logging.getLogger(name)
