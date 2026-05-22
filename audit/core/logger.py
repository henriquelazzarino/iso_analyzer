"""Structured logging for the audit tool. Stdlib only."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


_LOGGER_NAME = "iso25010"


def setup_logger(verbose: bool = False, log_file: Optional[Path] = None) -> logging.Logger:
    """Configure and return the application logger.

    Safe to call multiple times — handlers are reset to avoid duplicates.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(stream)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(str(log_file), encoding="utf-8")
            fh.setFormatter(fmt)
            fh.setLevel(logging.DEBUG)
            logger.addHandler(fh)
        except OSError:
            # Never crash because of logging
            pass

    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)
