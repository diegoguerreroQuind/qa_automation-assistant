from langchain_core.prompts import PromptTemplate

CYPRESS_GENERATOR_PROMPT = PromptTemplate.from_template(
    """Actúa como un Senior QA Automation Engineer experto en Cypress y TypeScript.
Tu tarea es generar el código de prueba E2E para el siguiente endpoint de una API.

AQUÍ ESTÁN LOS DATOS DEL ENDPOINT (Extraídos de Postman):
{endpoint_data}

REGLAS ESTRICTAS:
1. Usa 'cy.request()' para hacer la llamada a la API.
2. Escribe el código en TypeScript.
3. Incluye aserciones (expect) para validar el Status Code (ej. 200, 201).
4. Si hay un body en la petición, inclúyelo en el cy.request.
5. MANEJO DE VARIABLES: Si la URL contiene variables de Postman (ejemplo: {{{{url-host-marketing-notification}}}}), conviértelas a variables de entorno de Cypress dentro de un template string en TypeScript. 
   - Ejemplo de entrada: "{{{{url-api}}}}/users"
   - Ejemplo de salida: `${{Cypress.env('url-api')}}/users`
6. DEVUELVE ÚNICAMENTE CÓDIGO. No agregues saludos, ni bloques de markdown (como ```typescript). Solo el código crudo listo para ser guardado.

CÓDIGO CYPRESS:
"""
)