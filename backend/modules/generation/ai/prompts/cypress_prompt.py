# app/ai/prompts/cypress_prompt.py
from langchain_core.prompts import PromptTemplate

CYPRESS_CUCUMBER_PROMPT = PromptTemplate.from_template(
    """Actúa como un Senior QA Automation Engineer experto en Cypress, TypeScript y Cucumber BDD.
Tu tarea es generar pruebas automatizadas para el siguiente endpoint, combinando la información técnica de Postman con los Casos de Prueba definidos en Jira.

DATOS TÉCNICOS DEL ENDPOINT (Postman):
{endpoint_data}

CASOS DE PRUEBA A AUTOMATIZAR (Jira):
{casos_prueba_jira}

REGLAS ESTRICTAS Y CRÍTICAS:
1. Genera DOS bloques de código: el archivo Gherkin (.feature) y el Step Definitions (.ts).
2. En TypeScript, importa: `import {{ Given, When, Then }} from "@badeball/cypress-cucumber-preprocessor";`
3. Usa `cy.request()` en el paso 'When'.
4. CERO VARIABLES EN LOS STEPS (ANTI-COLISIONES): Para evitar el error "Multiple matching step definitions" en Cypress, ESTÁ TOTALMENTE PROHIBIDO usar parámetros dinámicos como {{string}} o {{int}} en los decoradores de TypeScript. TODO el texto de los steps debe estar literalmente QUEMADO (hardcoded).
5. SIN COMILLAS EN GHERKIN: NO uses comillas dobles ("") ni simples ('') dentro de las frases de los steps en el archivo .feature. Escribe las frases de forma plana.
6. MUTACIÓN DE DATOS: En TypeScript, programa la lógica para modificar el body/headers según el caso antes de hacer el cy.request.
7. NO AGREGUES FORMATO MARKDOWN EN EL CÓDIGO FINAL (sin ```gherkin ni ```ts).

USA EXACTAMENTE ESTE FORMATO DE RESPUESTA:

===FEATURE===
Feature: Probar {nombre_endpoint}

  # (Genera aquí todos los Scenarios basados en Jira)
  Scenario: [Descripción del escenario de Jira]
    Given que tengo los datos base para la peticion de {nombre_endpoint}
    And ajusto la peticion de {nombre_endpoint} para el caso [Breve nombre del caso sin usar comillas]
    When envio la peticion hacia {nombre_endpoint}
    Then el codigo de respuesta de {nombre_endpoint} debe ser [Codigo HTTP]

===STEPS===
import {{ Given, When, Then }} from "@badeball/cypress-cucumber-preprocessor";

// NUNCA uses {{string}} ni expresiones regulares. Copia y pega el texto EXACTO del .feature.

Given("que tengo los datos base para la peticion de {nombre_endpoint}", () => {{
    // setup
}});

Given("ajusto la peticion de {nombre_endpoint} para el caso [Breve nombre del caso sin usar comillas]", () => {{
    // mutación
}});

When("envio la peticion hacia {nombre_endpoint}", () => {{
    // cy.request
}});

Then("el codigo de respuesta de {nombre_endpoint} debe ser [Codigo HTTP]", () => {{
    // validación
}});
"""
)