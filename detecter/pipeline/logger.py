import logging
import sys

from .config import PipelineConfig


def get_logger(name: str, config: PipelineConfig) -> logging.Logger:
    logger = logging.getLogger(f"pipeline.{name}")

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(name)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
