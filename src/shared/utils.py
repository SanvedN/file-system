import os
import logging
import shutil
import structlog
from shared.config import settings


def get_log_level(level_str: str) -> int:
    """Convert string log level to logging module's level."""
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(
        level_str.upper(), logging.INFO
    )

def get_log_processors(format_str: str):
    """Return processor list based on format (e.g., 'json' or 'plain')."""
    base_processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.EventRenamer("log"),
    ]

    if format_str and format_str.lower() == "json":
        base_processors.append(structlog.processors.JSONRenderer())
    else:
        base_processors.append(structlog.dev.ConsoleRenderer())

    return base_processors


def setup_logger():
    """Configure structlog logger with env-based settings."""
    log_level_str = settings.file_repo_log_level
    log_format_str = settings.file_repo_log_format

    log_level = get_log_level(log_level_str)
    processors = get_log_processors(log_format_str)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        processors=processors,
    )

    return structlog.get_logger()

logger = setup_logger()

def tenant_folder_path(tenant_code: str) -> str:
    return os.path.join(settings.STORAGE_BASE_PATH, tenant_code)

def delete_tenant_folder(tenant_code: str) -> None:
    path = tenant_folder_path(tenant_code)
    if os.path.exists(path):
        shutil.rmtree(path)
        logger.info("Deleted tenant folder at %s", path)
    else:
        logger.debug("Tenant folder does not exist at %s", path)