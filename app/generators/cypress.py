import json
from pathlib import Path

def crear_estructura_cypress(destino: Path):
    """
    Crea la estructura de carpetas y archivos base para un proyecto de Cypress estable.
    """
    # Definimos las carpetas principales
    carpetas = [
        destino / "cypress" / "e2e",
        destino / "cypress" / "fixtures",
        destino / "cypress" / "support",
    ]

    # Creamos las carpetas (parents=True crea las carpetas intermedias si no existen)
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)

    # Creamos el package.json
    package_json = {
        "name": "cypress-api-tests",
        "version": "1.0.0",
        "description": "Pruebas E2E generadas automáticamente desde Postman",
        "scripts": {
            "test": "cypress open",
            "test:headless": "cypress run"
        },
        "devDependencies": {
            "cypress": "^13.0.0",
            "typescript": "^5.0.0"
        }
    }
    
    with open(destino / "package.json", "w", encoding="utf-8") as f:
        json.dump(package_json, f, indent=4)

    # Creamos el cypress.config.js (Estable para API Testing)
    cypress_config = """const { defineConfig } = require("cypress");

module.exports = defineConfig({
  e2e: {
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    supportFile: false, // Apagado porque son pruebas de API
  },
});
"""
    with open(destino / "cypress.config.js", "w", encoding="utf-8") as f:
        f.write(cypress_config)

    # Creamos el tsconfig.json perfecto para Cypress
    tsconfig = {
        "compilerOptions": {
            "target": "es5",
            "lib": ["es5", "dom"],
            "types": ["cypress", "node"],
            "baseUrl": "."
        },
        "include": ["**/*.ts"]
    }
    with open(destino / "tsconfig.json", "w", encoding="utf-8") as f:
        json.dump(tsconfig, f, indent=4)
        
    # Creamos un archivo de soporte vacío por si a futuro decides prender supportFile
    with open(destino / "cypress" / "support" / "e2e.ts", "w", encoding="utf-8") as f:
        f.write("// Archivo de soporte de Cypress para configuraciones globales\n")