# app/ai/prompts/jira.py
from langchain_core.prompts import PromptTemplate

JIRA_PARSER_PROMPT = PromptTemplate.from_template(
    """Eres un QA Automation Lead. Tu tarea es cruzar la descripción de una Historia de Usuario de Jira con un listado de endpoints de una API (Postman), y generar un JSON altamente estructurado.

Debes ignorar el texto de relleno de Jira, extraer el contexto de negocio, y AGRUPAR los Criterios de Aceptación vinculándolos EXACTAMENTE al 'nombre_peticion' del endpoint correspondiente que te proporciono en la lista de endpoints.
Extrae también el código HTTP esperado para cada criterio.

TEXTO CRUDO DE JIRA:
{descripcion_jira}

ENDPOINTS DISPONIBLES (API JSON):
{api_json_context}

Devuelve ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta (NO uses bloques de código markdown como ```json):
{{
  "contexto_negocio": "Resumen breve del contexto de la historia",
  "endpoints": [
    {{
      "nombre_endpoint": "Nombre EXACTO del endpoint sacado del API JSON (ej. enviar notificacion Email)",
      "criterios_aceptacion": [
        {{
          "id": 1,
          "descripcion_caso": "El endpoint debe retornar...",
          "codigo_http_esperado": 200
        }}
      ]
    }}
  ]
}}"""
)