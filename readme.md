app/
├── ai/
│   ├── generator.py        # 🧠 El cerebro sigue aquí
│   └── prompts/            # 📁 NUEVA CARPETA (reemplaza al archivo prompts.py)
│       ├── __init__.py     # Archivo vacío para que Python lo lea como módulo
│       ├── cypress.py      # Los prompts de generación de código
│       └── jira.py         # Los prompts de análisis de historias       # 📝 Los textos de la IA (NO SE TOCA)
├── commands/               # 🚀 NUEVA CARPETA (Los intermediarios de la terminal)
│   ├── __init__.py         
│   ├── postman.py          # (Comando extract)
│   ├── cypress.py          # (Comando scaffold)
│   ├── generate.py         # <--- (Comando generate) LE CAMBIAMOS EL NOMBRE AQUÍ
│   └── jira.py             # (Comando fetch-jira)
├── cli.py                  # 🎛️ El orquestador principal