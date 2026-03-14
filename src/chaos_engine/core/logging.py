"""
Logging Setup Module - Centralized logging configuration (Anti-Duplication).
"""
from __future__ import annotations

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = None, verbose: bool = False, log_dir: str = "logs") -> logging.Logger:
    """
    Configura el sistema de logging globalmente (en el Root Logger).

    Estrategia Anti-Duplicados:
    1. Limpia todos los handlers existentes del Root Logger.
    2. Configura los handlers (archivo/consola) SOLO en el Root Logger.
    3. Devuelve una instancia del logger solicitado para usar en el código.
    """
    # Crear directorio
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Si nos pasan un nombre, lo usamos para el archivo, sino "system"
    file_prefix = name if name else "system"
    log_file = str(Path(log_dir) / f"{file_prefix}_{timestamp}.log")

    # CRÍTICO: Eliminar cualquier handler previo (de librerías o ejecuciones anteriores)
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    console_level = "INFO" if verbose else "WARNING"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "file_fmt": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "console_fmt": {
                "format": "%(message)s",
            },
        },
        "handlers": {
            "file_handler": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "file_fmt",
                "filename": log_file,
                "encoding": "utf-8",
            },
            "console_handler": {
                "class": "logging.StreamHandler",
                "level": console_level,
                "formatter": "console_fmt",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["file_handler", "console_handler"],
        },
    }

    logging.config.dictConfig(config)

    # DEVOLVER LA INSTANCIA SOLICITADA
    # Si piden un logger específico, se lo damos, pero SIN handlers propios.
    # Confiará en la propagación hacia el Root que acabamos de configurar.
    if name:
        specific_logger = logging.getLogger(name)
        specific_logger.setLevel(logging.DEBUG)
        return specific_logger

    return logging.getLogger()
