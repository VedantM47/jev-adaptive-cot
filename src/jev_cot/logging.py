"""
jev_cot.logging
===============
Structured logging setup for the JEV-CoT pipeline.

Provides a dual-sink logger:
- **Console**: human-readable coloured output for development.
- **File**: JSON-lines (one JSON object per line) for machine processing,
  trajectory replay, and experiment auditing.

Usage::

    from jev_cot.logging import logger, setup_logging

    setup_logging(log_dir="logs", run_id="run_abc123")
    logger.info("Pipeline started", condition="vanilla")
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger  # re-exported for callers


def setup_logging(
    log_dir: str | Path = "logs",
    run_id: str = "default",
    level: str = "INFO",
) -> None:
    """
    Configure loguru with a console sink and a JSON-lines file sink.

    Call once at the start of each experiment run, passing the run's
    unique *run_id* so log files are namespaced per run.

    Args:
        log_dir:  Directory where log files are written.  Created if absent.
        run_id:   Unique identifier for this run (used in the filename).
        level:    Minimum log level (e.g. ``"DEBUG"``, ``"INFO"``).
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Remove loguru's default stderr handler so we control all output.
    logger.remove()

    # ── Console handler — human-readable, coloured ───────────────────────────
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "{message}"
        ),
        colorize=True,
        backtrace=True,
        diagnose=False,  # avoid leaking locals in production
    )

    # ── File handler — JSON-lines for machine processing ─────────────────────
    logger.add(
        log_path / f"{run_id}.log.jsonl",
        level=level,
        serialize=True,  # loguru serialize=True → one JSON object per line
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        backtrace=False,
        diagnose=False,
    )


__all__ = ["logger", "setup_logging"]
