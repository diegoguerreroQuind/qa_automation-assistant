# app/config.py
import json
from pathlib import Path

# Ruta absoluta al config.json en la raíz del proyecto
# (sube dos niveles desde app/config.py → raíz del proyecto)
_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def cargar_config() -> dict:
    """
    Lee y devuelve el contenido completo de config.json.
    Lanza un error claro si el archivo no existe o está malformado.
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de configuración en: {_CONFIG_PATH}\n"
            f"Asegúrate de que 'config.json' exista en la raíz del proyecto."
        )
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"El archivo config.json tiene un formato JSON inválido: {e}")


def obtener_config_jira() -> dict:
    """Devuelve solo la sección 'jira' del config."""
    return cargar_config().get("jira", {})


def obtener_rutas() -> dict:
    """Devuelve solo la sección 'rutas' del config."""
    return cargar_config().get("rutas", {})


def obtener_config_ia() -> dict:
    """Devuelve solo la sección 'ia' del config."""
    return cargar_config().get("ia", {})