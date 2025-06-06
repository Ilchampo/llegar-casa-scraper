"""Logging configuration for the scraper application."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured information."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "llegar-casa-scrapper",
            "environment": settings.ENVIRONMENT.value,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, 'license_plate'):
            log_data["license_plate"] = record.license_plate
        if hasattr(record, 'driver_name'):
            log_data["driver_name"] = record.driver_name
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, 'client_ip'):
            log_data["client_ip"] = record.client_ip
        
        formatted_pairs = []
        for key, value in log_data.items():
            if isinstance(value, str):
                formatted_pairs.append(f'{key}="{value}"')
            else:
                formatted_pairs.append(f'{key}={value}')
        
        return " ".join(formatted_pairs)


def setup_logging() -> None:
    """Set up application logging configuration."""
    
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    root_logger.handlers.clear()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = StructuredFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    file_handler = logging.FileHandler(
        logs_dir / "app.log",
        mode="a",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = StructuredFormatter()
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    error_handler = logging.FileHandler(
        logs_dir / "error.log",
        mode="a",
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = StructuredFormatter()
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)
    
    scraper_logger = logging.getLogger("scraper")
    scraper_handler = logging.FileHandler(
        logs_dir / "scraper.log",
        mode="a",
        encoding="utf-8"
    )
    scraper_handler.setLevel(logging.DEBUG)
    scraper_handler.setFormatter(StructuredFormatter())
    scraper_logger.addHandler(scraper_handler)
    scraper_logger.setLevel(logging.DEBUG)
    
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configuration complete", extra={
        "environment": settings.ENVIRONMENT.value,
        "app_version": settings.APP_VERSION
    })


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class RequestLogger:
    """Context manager for request-specific logging."""
    
    def __init__(self, request_type: str, **kwargs):
        self.request_type = request_type
        self.extra_data = kwargs
        self.logger = get_logger(f"request.{request_type}")
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting {self.request_type} request", extra=self.extra_data)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
        
        extra_data = {**self.extra_data, "duration_ms": duration_ms}
        
        if exc_type is None:
            self.logger.info(f"Completed {self.request_type} request", extra=extra_data)
        else:
            self.logger.error(
                f"Failed {self.request_type} request: {exc_val}", 
                extra=extra_data,
                exc_info=True
            )
    
    def log(self, message: str, level: str = "info", **kwargs):
        """Log a message within this request context."""
        extra_data = {**self.extra_data, **kwargs}
        getattr(self.logger, level)(message, extra=extra_data) 