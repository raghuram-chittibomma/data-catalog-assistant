"""
Logging configuration.
"""

import logging
import logging.config
from pathlib import Path
from typing import Dict, Any


def setup_logging(config_path: str = None, level: str = "INFO") -> None:
    """
    Setup logging configuration.

    Args:
        config_path: Path to logging config file (YAML or JSON)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if config_path and Path(config_path).exists():
        # Load from config file
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    else:
        # Basic configuration
        logging.basicConfig(
            level=getattr(logging, level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("bdw_rag.log")
            ]
        )
    logging.info("Logging configured")
