"""Logging configuration."""

from __future__ import annotations

import logging
import logging.handlers
import sys

from .core.config_store import config_dir


def setup_logging(
    debug: bool,
) -> None:
    log_dir = (
        config_dir()
        / "logs"
    )

    log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        log_dir
        / "multitapkey.log"
    )

    level = (
        logging.DEBUG
        if debug
        else logging.INFO
    )

    handler = (
        logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=512 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    )

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        )
    )

    root = logging.getLogger()
    root.setLevel(level)

    for existing in list(
        root.handlers
    ):
        root.removeHandler(
            existing
        )
        existing.close()

    root.addHandler(handler)

    def excepthook(
        exc_type,
        exc_value,
        exc_traceback,
    ):
        logging.getLogger(
            "uncaught"
        ).critical(
            "uncaught exception",
            exc_info=(
                exc_type,
                exc_value,
                exc_traceback,
            ),
        )

    sys.excepthook = excepthook
