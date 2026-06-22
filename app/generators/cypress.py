import json
from pathlib import Path


def crear_estructura_cypress(destino: Path, env_vars: dict | None = None) -> None:
    """
    Creates the full Cypress + Cucumber BDD project structure.

    Args:
        destino:   Target directory where the project will be scaffolded.
        env_vars:  Dict of Postman environment variables to write into
                   cypress.env.json so tests run without manual setup.
                   Pass None or {} when no environment file was uploaded.
    """
    # ------------------------------------------------------------------
    # 1. Directory structure
    # ------------------------------------------------------------------
    carpetas = [
        destino / "cypress" / "e2e" / "features",
        destino / "cypress" / "e2e" / "step_definitions",
        destino / "cypress" / "fixtures",
        destino / "cypress" / "services",
        destino / "cypress" / "support",
    ]
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 2. package.json — includes @types/node to avoid TS compilation errors
    # ------------------------------------------------------------------
    package_json = {
        "name": "cypress-api-tests-cucumber",
        "version": "1.0.0",
        "description": "Pruebas BDD generadas automáticamente desde Postman",
        "scripts": {
            "test": "cypress open",
            "test:headless": "cypress run",
            "test:headless:report": "cypress run --reporter mochawesome"
        },
        "devDependencies": {
            "cypress": "^13.0.0",
            "typescript": "^5.0.0",
            "@types/node": "^20.0.0",
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
        json.dump(package_json, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 3. cypress.config.js
    # ------------------------------------------------------------------
    cypress_config = """\
const { defineConfig } = require("cypress");
const createBundler = require("@bahmutov/cypress-esbuild-preprocessor");
const { addCucumberPreprocessorPlugin } = require("@badeball/cypress-cucumber-preprocessor");
const { createEsbuildPlugin } = require("@badeball/cypress-cucumber-preprocessor/esbuild");

module.exports = defineConfig({
  e2e: {
    specPattern: "cypress/e2e/features/**/*.feature",
    supportFile: "cypress/support/e2e.ts",
    responseTimeout: 30000,
    requestTimeout: 30000,
    async setupNodeEvents(on, config) {
      await addCucumberPreprocessorPlugin(on, config);
      on(
        "file:preprocessor",
        createBundler({
          plugins: [createEsbuildPlugin(config)],
        })
      );
      return config;
    },
  },
});
"""
    with open(destino / "cypress.config.js", "w", encoding="utf-8") as f:
        f.write(cypress_config)

    # ------------------------------------------------------------------
    # 4. tsconfig.json
    # ------------------------------------------------------------------
    tsconfig = {
        "compilerOptions": {
            "target": "es5",
            "lib": ["es5", "dom"],
            "types": ["cypress", "node", "@badeball/cypress-cucumber-preprocessor"],
            "baseUrl": ".",
            "resolveJsonModule": True,
            "esModuleInterop": True
        },
        "include": ["**/*.ts"]
    }
    with open(destino / "tsconfig.json", "w", encoding="utf-8") as f:
        json.dump(tsconfig, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 5. cypress/support/e2e.ts — global config for all tests
    # ------------------------------------------------------------------
    support_content = """\
// Global Cypress support file — runs before every spec.
// Add reusable commands or global configuration here.

// Silence uncaught exception errors that don't belong to the test
Cypress.on("uncaught:exception", () => false);
"""
    with open(destino / "cypress" / "support" / "e2e.ts", "w", encoding="utf-8") as f:
        f.write(support_content)

    # ------------------------------------------------------------------
    # 6. cypress.env.json — environment variables from Postman
    #    Written even when empty so Cypress.env() never throws.
    # ------------------------------------------------------------------
    with open(destino / "cypress.env.json", "w", encoding="utf-8") as f:
        json.dump(env_vars or {}, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 7. README.md — step-by-step run instructions
    # ------------------------------------------------------------------
    has_vars = bool(env_vars)
    env_note = (
        "Las variables de entorno de Postman fueron importadas automáticamente en `cypress.env.json`."
        if has_vars
        else (
            "⚠️  No se detectó archivo de entorno Postman.\n"
            "   Abre `cypress.env.json` y agrega las variables necesarias, por ejemplo:\n"
            "   ```json\n"
            '   { "baseUrl": "https://tu-servidor.com" }\n'
            "   ```"
        )
    )
    readme = f"""\
# Cypress API Tests — BDD (Cucumber)

Proyecto generado automáticamente por **QA AI Assistant**.

## Requisitos

- Node.js >= 18
- npm >= 9

## Instalación

```bash
npm install
```

## Variables de entorno

{env_note}

También puedes sobrescribir cualquier variable desde la línea de comandos:

```bash
npx cypress run --env baseUrl=https://otro-servidor.com
```

## Ejecución

| Modo | Comando |
|------|---------|
| Interfaz visual (debug) | `npm test` |
| Headless (CI/CD) | `npm run test:headless` |

## Estructura

```
cypress-project/
├── cypress/
│   ├── e2e/
│   │   ├── features/          ← archivos .feature (Gherkin)
│   │   └── step_definitions/  ← implementación TypeScript
│   ├── fixtures/              ← datos de prueba estáticos
│   ├── services/              ← helpers reutilizables
│   └── support/
│       └── e2e.ts             ← configuración global
├── cypress.config.js
├── cypress.env.json           ← variables de entorno (⚠️ no subir a git)
├── package.json
└── tsconfig.json
```

> **Nota de seguridad:** agrega `cypress.env.json` a tu `.gitignore` si contiene tokens o URLs sensibles.
"""
    with open(destino / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)