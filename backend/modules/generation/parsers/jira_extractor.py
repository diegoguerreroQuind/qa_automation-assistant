# app/parsers/jira_extractor.py
from jira import JIRA
from typing import Dict

def extraer_historia_jira(server: str, email: str, token: str, issue_key: str) -> Dict[str, str]:
    """
    Se conectará a tu Jira, buscará el ticket y nos devolverá la descripción.
    """
    try:
        # Autenticación básica con Jira
        jira_client = JIRA(server=server, basic_auth=(email, token))
        
        # Buscamos el ticket específico (ej. PROY-123)
        historia = jira_client.issue(issue_key)
        
        # Extraemos el resumen y la descripción (donde están tus criterios)
        resumen = historia.fields.summary
        descripcion = historia.fields.description
        
        # Si la descripción está vacía, evitamos que el programa explote
        if not descripcion:
            descripcion = "La historia no tiene descripción."

        return {
            "key": historia.key,
            "resumen": resumen,
            "descripcion": descripcion
        }
        
    except Exception as e:
        raise Exception(f"Fallo al comunicarse con Jira para el ticket {issue_key}: {e}")