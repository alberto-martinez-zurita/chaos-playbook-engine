"""
Logging Setup Module - Centralized logging configuration (Anti-Duplication).
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

def setup_logger(name: str = None, verbose: bool = False, log_dir: str = "logs"):
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
    log_file = Path(log_dir) / f"{file_prefix}_{timestamp}.log"

    # 1. OBTENER Y LIMPIAR EL ROOT LOGGER
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 🔥 CRÍTICO: Eliminar cualquier handler previo (de librerías o ejecuciones anteriores)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 2. CREAR HANDLERS
    
    # A) Archivo: Guarda TODO (DEBUG)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_fmt)
    
    # B) Consola: Limpia y configurable
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO if verbose else logging.WARNING)
    console_fmt = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_fmt)

    # 3. AÑADIR HANDLERS SOLO AL ROOT
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 4. DEVOLVER LA INSTANCIA SOLICITADA
    # Si piden un logger específico, se lo damos, pero SIN handlers propios.
    # Confiará en la propagación hacia el Root que acabamos de configurar.
    if name:
        specific_logger = logging.getLogger(name)
        specific_logger.setLevel(logging.DEBUG)
        return specific_logger
        
    return root_logger