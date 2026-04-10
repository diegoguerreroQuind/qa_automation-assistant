import os
import ssl
import json 
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from app.ai.prompts.cypress_prompt import CYPRESS_CUCUMBER_PROMPT
from app.ai.prompts.jira_prompt import JIRA_PARSER_PROMPT

# --- PARCHE PARA REDES CORPORATIVAS ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# --------------------------------------

load_dotenv()

# --- ACTUALIZADO: Ahora recibe casos_jira (por defecto vacío para no romper usos anteriores) ---
def generar_test_cypress(endpoint_data: dict, casos_jira: list = None) -> dict:
    """
    Usa Gemini para generar código BDD y devuelve un diccionario con:
    {'feature': 'código gherkin', 'steps': 'código typescript'}
    """
    if casos_jira is None:
        casos_jira = []

    llm = ChatGoogleGenerativeAI(
        model="gemini-pro-latest", 
        temperature=0.1
    )
    
    chain = CYPRESS_CUCUMBER_PROMPT | llm | StrOutputParser()
    
    # --- ACTUALIZADO: Le pasamos los casos de Jira a la IA ---
    respuesta_cruda = chain.invoke({
        "endpoint_data": str(endpoint_data),
        "nombre_endpoint": endpoint_data.get("nombre_peticion", "endpoint_desconocido"),
        "casos_prueba_jira": str(casos_jira) if casos_jira else "Generar solo un Happy Path exitoso." 
    })
    
    # Limpiamos basura de markdown por si la IA desobedece
    respuesta_cruda = respuesta_cruda.replace("```gherkin", "").replace("```typescript", "").replace("```ts", "").replace("```", "").strip()
    
    # Separamos la respuesta usando los delimitadores que le dimos en el prompt
    try:
        partes = respuesta_cruda.split("===STEPS===")
        feature_part = partes[0].replace("===FEATURE===", "").strip()
        steps_part = partes[1].strip()
        
        return {
            "feature": feature_part,
            "steps": steps_part
        }
    except IndexError:
        raise ValueError("La IA no devolvió el formato esperado con los delimitadores.")


def estructurar_descripcion_jira(descripcion_cruda: str, api_json_context: str) -> dict:
    """
    Usa Gemini para cruzar el texto crudo de Jira con los endpoints de la API, 
    devolviendo un diccionario estructurado.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-pro-latest", 
        temperature=0.0 # Temperatura 0 para precisión absoluta
    )
    
    chain = JIRA_PARSER_PROMPT | llm | StrOutputParser()
    
    # Pasamos ambos contextos a la IA
    respuesta_cruda = chain.invoke({
        "descripcion_jira": descripcion_cruda,
        "api_json_context": api_json_context
    })
    
    respuesta_limpia = respuesta_cruda.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(respuesta_limpia)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini no devolvió un JSON válido. Respuesta: {respuesta_limpia}\nError: {e}")