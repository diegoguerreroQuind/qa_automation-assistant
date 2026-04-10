
# Framework QA + I.A.

Un framework innovador impulsado por Inteligencia Artificial diseñado para potenciar a los ingenieros de pruebas en la generación de automatización enfocada a APIs, integrando Python, Cypress, Cucumber y modelos de IA generativa.

---

## 📖 Tabla de Contenidos
- [Concepción del Proceso](#concepción-del-proceso)
- [Arquitectura y Componentes del proyecto](#Arquitectura-y-Componentes-del-proyecto)
- [Guía de Uso](#guía-de-uso)

---

## Concepción del Proceso

Conforme evolucionan los asistentes de IA y los modelos agénticos integrados a los entornos de desarrollo (IDE), los procesos de calidad de software necesitan evolucionar al mismo ritmo. La aceleración en el ciclo de desarrollo ha generado nuevos desafíos en la industria:

* **El Cuello de Botella:** La rápida producción de código generada por la IA desde el lado del desarrollo ha superado la capacidad de revisión humana, generando largas colas de espera para la revisión funcional por parte de los ingenieros QA.
* **Pérdida de Profundidad Técnica:** Aunque el código generado por IA es funcional en primera instancia, a menudo carece de refinamiento técnico. Esto provoca un aumento de *bugs* colaterales que difícilmente se detectan desde una fase de pruebas unitarias.

> **La Solución:** Este contexto disruptivo da origen a un **Framework basado en IA** que asiste al ingeniero de pruebas en la creación de código enfocado a la validación de APIs (el punto de entrada crítico de casi cualquier arquitectura de software moderna).

El framework opera bajo el paradigma de **"Human-in-the-loop"**. La máquina asume la carga de generar rápidamente el código base, mientras que el ingeniero QA evoluciona hacia un rol de **Arquitecto de Procesos**, centrándose en la auditoría del código, la coherencia de las pruebas y la validación de la seguridad.

---

## Arquitectura y Componentes del proyecto

El framework se divide en un flujo de trabajo estructurado en 6 fases principales que conectan la documentación de las APIs y los requerimientos del negocio directamente con el código de prueba.

### 1. Activación del Entorno (Python)
Se inicializa un entorno virtual para garantizar el aislamiento y correcto manejo de las dependencias del core del proyecto.

### 2. Extracción y Normalización (Postman)
Proceso de extracción y transformación (ETL ligero) que toma las colecciones de Postman (`collection.json` y `environment.json`) y las consolida en un artefacto estructurado central (`api.json`). Este archivo normaliza y expone todos los endpoints, métodos, headers y parámetros.

### 3. Generación del Scaffolding (Cypress + Cucumber)
Utilizando `api.json` como fuente de verdad, el framework construye de forma automática toda la estructura base del proyecto de pruebas en Cypress, asegurando compatibilidad con metodologías BDD (Cucumber). Esto incluye la creación de carpetas, archivos base y la configuración inicial.

### 4. Ingesta de Criterios de Aceptación (Jira)
Mediante una integración directa con Jira, se extraen las Historias de Usuario (HU). Un proceso de IA con técnicas de *grounding* interpreta los criterios de aceptación y construye un contexto estructurado en el archivo `inputContext.json`.

### 5. Generación Automatizada de Casos de Prueba (IA)
El núcleo inteligente del framework. Utilizando modelos de IA (actualmente basado en GEMINI), se cruza el diseño de la API (`api.json`) con los requerimientos del negocio (`inputContext.json`) para redactar automáticamente archivos `.feature` en sintaxis Gherkin.

### 6. Configuración del Entorno de Ejecución (Cypress)
Parametrización final de archivos (como `tsconfig.json`) para inyectar variables de entorno, mapeo de endpoints y configuraciones dinámicas de ejecución basadas en las credenciales específicas del entorno.

---

## Guía de Uso

A continuación, se detallan los comandos de consola (`CLI`) necesarios para ejecutar cada fase del framework:

### 2.1 Activar el entorno de ejecución
Aisla las dependencias del proyecto de Python.
```bash
source venv/bin/activate
```

### 2.2 Extraer y normalizar la colección
Genera el artefacto central api.json a partir de tu archivo fuente de Postman.
```
python main.py extract -c marketing.json -o api.json
```

### 2.3 Generar el Scaffolding
Despliega la estructura inicial del proyecto para Cypress y Cucumber en el directorio destino.
```
python main.py scaffold -d ./mi-proyecto-qa
```

### 2.4 Obtener contexto de pruebas desde Jira
Analiza la Historia de Usuario conectada para extraer criterios de aceptación.
```
python main.py fetch-jira
```

### 2.5 Generar los Casos de Prueba (Gherkin)
Ejecuta la IA para construir los escenarios de prueba dentro de la estructura de Cucumber.
```
python main.py generate -j api.json -d ./mi-proyecto-qa
```

### 2.6 Configurar el entorno de ejecución final
Aplica las configuraciones dinámicas y variables para preparar Cypress para la ejecución.
```
python main.py generate -j api.json -e entorno.json -d ./mi-proyecto-qa
```

## 3 Estructura del proyecto
### 📂 Estructura del Proyecto

```text
app/
├── ai/
│   ├── generator.py        # El cerebro sigue aquí
│   └── prompts/            # NUEVA CARPETA (reemplaza al archivo prompts.py)
│       ├── __init__.py     # Archivo vacío para que Python lo lea como módulo
│       ├── cypress.py      # Los prompts de generación de código
│       └── jira.py         # Los prompts de análisis de historias y textos de IA (NO SE TOCA)
├── commands/               # NUEVA CARPETA (Los intermediarios de la terminal)
│   ├── __init__.py         
│   ├── postman.py          # Comando: extract
│   ├── cypress.py          # Comando: scaffold
│   ├── generate.py         # Comando: generate
│   └── jira.py             # Comando: fetch-jira
├── generators/             
│   └── cypress.py          # Estructurador de la estructura principal de Cypress
├── parsers/                     
│   ├── enviroment.py          # Extrae contexto del archivo json
│   ├── jira_extractor.py      # Adquiere los criterios de aceptación de la hu
│   └── postman.py             # Extrae la data del archivo json original
└── cli.py                  # El orquestador principal de comandos

```

---

<h1 align="center">Framework QA + IA</h1>

<p align="center">
  <img src="https://quind.io/wp-content/uploads/2024/02/logoquind-white.png" width="240"/>
</p>

<p align="center">
  <strong>Automatización inteligente de APIs con IA</strong>
</p>

---