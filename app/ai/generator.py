import os
import ssl
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser  # <-- NUEVO IMPORT
from app.ai.prompts import CYPRESS_GENERATOR_PROMPT

# --- PARCHE PARA REDES CORPORATIVAS CON PROXY/VPN ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------------------------------------

load_dotenv()

def generar_test_cypress(endpoint_data: dict) -> str:
    """
    Toma un diccionario con los datos limpios de un endpoint y usa Gemini
    vía LangChain para generar el código de prueba en Cypress.
    """
    # Usamos el modelo que elegiste (le quité el prefijo "models/" que a veces da problemas)
    llm = ChatGoogleGenerativeAI(
        model="gemini-pro-latest", 
        temperature=0.1
    )
    
    # Añadimos el StrOutputParser al final de la cadena de LangChain
    chain = CYPRESS_GENERATOR_PROMPT | llm | StrOutputParser()
    
    # Al usar StrOutputParser, "respuesta" ya es 100% un string garantizado
    respuesta = chain.invoke({"endpoint_data": str(endpoint_data)})
    
    # Ahora el replace funcionará perfecto
    codigo_limpio = respuesta.replace("```typescript", "").replace("```ts", "").replace("```", "").strip()
    
    return codigo_limpio