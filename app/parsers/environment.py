import json
from pathlib import Path
from typing import Dict

def extraer_variables_entorno(ruta_env: Path) -> Dict[str, str]:
    """
    Lee un archivo JSON de entorno de Postman y extrae las variables activas
    en un formato compatible con cypress.env.json ({ "llave": "valor" }).
    """
    variables_limpias = {}
    
    with open(ruta_env, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # El JSON de entorno de Postman guarda las variables en la llave "values"
    valores = data.get("values", [])

    for item in valores:
        # Extraemos solo las variables que no estén desactivadas en Postman
        if item.get("enabled", True):
            key = item.get("key")
            value = item.get("value")
            if key:
                variables_limpias[key] = value

    return variables_limpias