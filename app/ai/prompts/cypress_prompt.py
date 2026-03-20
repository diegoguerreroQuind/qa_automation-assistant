# app/ai/prompts/cypress.py
from langchain_core.prompts import PromptTemplate

CYPRESS_CUCUMBER_PROMPT = PromptTemplate.from_template(
    """Actúa como un Senior QA Automation Engineer experto en Cypress, TypeScript y Cucumber BDD.
Tu tarea es generar las pruebas automatizadas para el siguiente endpoint de una API.

DATOS DEL ENDPOINT (Postman):
{endpoint_data}

REGLAS ESTRICTAS:
1. Debes generar DOS bloques de código: el archivo Gherkin y el archivo de Step Definitions.
2. IMPORTANTE: En el archivo TypeScript, importa los steps usando EXACTAMENTE esto:
   `import {{ Given, When, Then }} from "@badeball/cypress-cucumber-preprocessor";`
3. Usa `cy.request()` en el paso 'When'.
4. MANEJO DE VARIABLES: Si la URL contiene variables de Postman (ej. {{{{url-host}}}}), conviértelas a `${{Cypress.env('url-host')}}` en el TypeScript.
5. NO AGREGUES FORMATO MARKDOWN.
6. UNICIDAD: Debes incluir el nombre de la petición '{nombre_endpoint}' dentro de las frases de los steps (Given, When, Then) para evitar choques con otras pruebas.

USA EXACTAMENTE ESTE FORMATO DE RESPUESTA:

===FEATURE===
Feature: Probar {nombre_endpoint}
  Scenario: Ejecutar exitosamente {nombre_endpoint}
    Given que tengo los datos para '{nombre_endpoint}'
    When envío la petición hacia '{nombre_endpoint}'
    Then el código de respuesta para '{nombre_endpoint}' debe ser exitoso

===STEPS===
import {{ Given, When, Then }} from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos para '{nombre_endpoint}'", () => {{
    // setup si es necesario
}});

When("envío la petición hacia '{nombre_endpoint}'", () => {{
    // cy.request(...)
}});

Then("el código de respuesta para '{nombre_endpoint}' debe ser exitoso", () => {{
    // validaciones
}});
"""
)