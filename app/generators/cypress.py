import json
from pathlib import Path

def crear_estructura_cypress(destino: Path):
    """
    Crea la estructura de carpetas y archivos base para un proyecto de Cypress con Cucumber BDD.
    """
    # 1. Definimos las carpetas con tu nueva arquitectura escalable
    carpetas = [
        destino / "cypress" / "e2e" / "features",
        destino / "cypress" / "e2e" / "step_definitions",
        destino / "cypress" / "fixtures",
        destino / "cypress" / "services",
        destino / "cypress" / "support",
    ]

    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)

    # 2. Creamos el package.json (Apuntando a los nuevos step_definitions)
    package_json = {
        "name": "cypress-api-tests-cucumber",
        "version": "1.0.0",
        "description": "Pruebas BDD generadas automáticamente desde Postman",
        "scripts": {
            "test": "cypress open",
            "test:headless": "cypress run"
        },
        "devDependencies": {
            "cypress": "^13.0.0",
            "typescript": "^5.0.0",
            "@badeball/cypress-cucumber-preprocessor": "^20.0.0",
            "@bahmutov/cypress-esbuild-preprocessor": "^2.2.0",
            "esbuild": "^0.20.0"
        },
        "cypress-cucumber-preprocessor": {
            "stepDefinitions": [
                "cypress/e2e/step_definitions/**/*.{js,ts}"
            ]
        }
    }
    
    with open(destino / "package.json", "w", encoding="utf-8") as f:
        json.dump(package_json, f, indent=4)

    # 3. Creamos el cypress.config.js (Apuntando a la carpeta de features)
    cypress_config = """const { defineConfig } = require("cypress");
const createBundler = require("@bahmutov/cypress-esbuild-preprocessor");
const { addCucumberPreprocessorPlugin } = require("@badeball/cypress-cucumber-preprocessor");
const { createEsbuildPlugin } = require("@badeball/cypress-cucumber-preprocessor/esbuild");

module.exports = defineConfig({
  e2e: {
    specPattern: "cypress/e2e/features/**/*.feature", // Enrutado a tu carpeta específica
    async setupNodeEvents(on, config) {
      // Configuramos el plugin de Cucumber
      await addCucumberPreprocessorPlugin(on, config);
      
      // Configuramos esbuild para compilar los steps
      on(
        "file:preprocessor",
        createBundler({
          plugins: [createEsbuildPlugin(config)],
        })
      );

      return config;
    },
    supportFile: false, // Apagado porque son pruebas de API
  },
});
"""
    with open(destino / "cypress.config.js", "w", encoding="utf-8") as f:
        f.write(cypress_config)

    # 4. Creamos el tsconfig.json perfecto para Cypress + Cucumber
    tsconfig = {
        "compilerOptions": {
            "target": "es5",
            "lib": ["es5", "dom"],
            "types": ["cypress", "node", "@badeball/cypress-cucumber-preprocessor"],
            "baseUrl": ".",
            "resolveJsonModule": True
        },
        "include": ["**/*.ts"]
    }
    with open(destino / "tsconfig.json", "w", encoding="utf-8") as f:
        json.dump(tsconfig, f, indent=4)
        
    # 5. Creamos un archivo de soporte vacío
    with open(destino / "cypress" / "support" / "e2e.ts", "w", encoding="utf-8") as f:
        f.write("// Archivo de soporte de Cypress para configuraciones globales\n")