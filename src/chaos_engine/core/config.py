# config/config_loader.py

"""
Sistema de carga de configuración desde archivos YAML.
Soporta múltiples entornos (dev/prod) con variables de entorno.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

class ConfigLoader:
    """
    Carga configuración desde archivos YAML basado en el entorno.
    
    Uso:
        config = ConfigLoader.load()
        model = config['agent']['model']
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Try cwd first (works for any install method), then fall back to __file__
            cwd_config = Path.cwd() / "config"
            if cwd_config.exists():
                self.config_dir = cwd_config
            else:
                # Derive from source layout: src/chaos_engine/core/config.py → ROOT/config
                project_root = Path(__file__).resolve().parents[3]
                self.config_dir = project_root / "config"

        if not self.config_dir.exists():
            import logging
            logging.getLogger(__name__).warning("Config dir not found at %s", self.config_dir)
        
    def load(self, environment: str = None) -> Dict[str, Any]:
        """
        Carga configuración del entorno especificado.
        """
        load_dotenv()
        
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "dev").lower()
        
        # Normalizar alias
        if environment == "development": environment = "dev"
        if environment == "production": environment = "prod"
        
        # ✅ INTENTO 1: Buscar nombre moderno (dev.yaml)
        config_file = self.config_dir / f"{environment}.yaml"
        
        # ✅ INTENTO 2: Buscar nombre legacy (dev_config.yaml) si el moderno falla
        if not config_file.exists():
             config_file_legacy = self.config_dir / f"{environment}_config.yaml"
             if config_file_legacy.exists():
                 config_file = config_file_legacy

        if not config_file.exists():
            raise FileNotFoundError(
                f"❌ No se encontró el archivo de configuración: {config_file}\n"
                f"   Archivos disponibles en {self.config_dir}:\n"
                f"   {list(self.config_dir.glob('*.yaml'))}"
            )
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        config = self._enrich_with_env_vars(config)
        return config
    
    def _enrich_with_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Añade variables de entorno necesarias para ADK.
        """
        # API Key (requerida)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "⚠️ No se encontró GOOGLE_API_KEY en el archivo .env\n"
                "Por favor crea un archivo '.env' en la raíz del proyecto con:\n"
                "GOOGLE_API_KEY=tu_api_key_aqui"
            )
        
        # Configurar variables de entorno para ADK
        os.environ["GOOGLE_API_KEY"] = api_key
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        
        # Añadir al config para referencia
        config['api_key'] = api_key
        config['use_vertex_ai'] = False

        # 2. MOCK MODE (Nuevo)
        # Lee del .env, default False si no existe
        mock_mode_env = os.getenv("MOCK_MODE", "false").lower()
        config['mock_mode'] = mock_mode_env in ("true", "1", "yes")
        
        return config
    
    def _validate_config(self, config: Dict[str, Any]):
        """
        Valida que la configuración tenga los campos requeridos.
        """
        required_keys = ['environment', 'agent', 'session_service']
        
        for key in required_keys:
            if key not in config:
                raise ValueError(
                    f"❌ Configuración inválida: falta la clave '{key}'\n"
                    f"   Claves presentes: {list(config.keys())}"
                )
        
        # Validar subcampos
        if 'model' not in config['agent']:
            raise ValueError("❌ Configuración 'agent.model' no encontrada")
        
        if 'db_url' not in config['session_service']:
            raise ValueError("❌ Configuración 'session_service.db_url' no encontrada")


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

def load_config(environment: str = None) -> Dict[str, Any]:
    """
    Función de conveniencia para cargar configuración.
    
    Args:
        environment: 'dev' o 'prod'. Si None, usa ENV variable o 'dev'.
    
    Returns:
        Dict con configuración
        
    Example:
        config = load_config()
        config = load_config('prod')
    """
    loader = ConfigLoader()
    return loader.load(environment)


def get_model_name(config: Dict[str, Any]) -> str:
    """Extrae el nombre del modelo de la configuración."""
    return config['agent']['model']


def get_db_url(config: Dict[str, Any]) -> str:
    """Extrae la URL de la base de datos de la configuración."""
    return config['session_service']['db_url']


def get_runner_type(config: Dict[str, Any]) -> str:
    """Extrae el tipo de runner de la configuración."""
    return config.get('runner', {}).get('type', 'InMemoryRunner')


# ============================================================================
# TEST DE CARGA
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 TEST DE CARGA DE CONFIGURACIÓN")
    print("="*80 + "\n")
    
    # Test dev config
    print("--- Cargando dev_config.yaml ---")
    dev_config = load_config('dev')
    print(f"   Entorno: {dev_config['environment']}")
    print(f"   Modelo: {get_model_name(dev_config)}")
    print(f"   DB URL: {get_db_url(dev_config)}")
    print(f"   Runner: {get_runner_type(dev_config)}")
    
    print("\n" + "="*80)
    print("✅ Test completado")
    print("="*80 + "\n")