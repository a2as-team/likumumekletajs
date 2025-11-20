"""
Logging configuration for the Latvian Legal Changes Multi-Agent System.
Sets up DEBUG-level logging for development and local monitoring.
"""

import logging
import os
from pathlib import Path


def setup_logging(log_level: str = "DEBUG", log_file: str = "agent_debug.log"):
    """
    Configure logging for ADK agents with DEBUG level support.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_path = log_dir / log_file
    
    # Remove old log file if it exists
    if log_path.exists():
        log_path.unlink()
    
    # Get root logger and clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s"
    )
    
    # Create and configure file handler
    file_handler = logging.FileHandler(log_path, mode='w')
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    
    # Create and configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Also configure specific loggers we know about
    for logger_name in ['tools.likumi_scraper', 'tools.memory_tools', 'agents', 'google.adk']:
        specific_logger = logging.getLogger(logger_name)
        specific_logger.setLevel(getattr(logging, log_level.upper()))
    
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Logging configured at {log_level} level")
    logger.info(f"📝 Log file: {log_path.absolute()}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(name)
