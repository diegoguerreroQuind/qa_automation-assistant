# Colección Postman — QA AI Assistant API

Verificación manual completa del backend FastAPI que orquesta el pipeline
**Postman + Jira → Cypress BDD**.

## 📦 Archivos

| Archivo | Contenido |
|---------|-----------|
| `qa-ai-assistant.postman_collection.json`  | 38 requests organizados en 9 carpetas (flujo + casos de error) |
| `qa-ai-assistant.postman_environment.json` | Entorno listo con todas las variables |

## 🚀 Importar (60 segundos)

1. Abre Postman → **Import** → arrastra los DOS archivos.
2. Arriba a la derecha, selecciona el entorno **"QA AI Assistant — Local Dev"**.
3. Edita el entorno y pon tu `password` real.
4. Asegura que el backend esté arriba: `GET {{baseUrl}}/health` → `{"status":"ok"}`.

## 🔑 Auto-magia

Algunos requests guardan variables automáticamente, así que **no copias IDs a mano**:

| Request                                    | Variable guardada       |
|--------------------------------------------|-------------------------|
| `🔐 Auth → Login`                          | `access_token`          |
| `📁 Projects → Create Project`             | `project_id`            |
| `🎫 Jira → POST /jira/tickets`             | `issue_key` (el primero) |
| `⚙️ Pipeline → 1️⃣ Create Execution`        | `execution_id`          |
| `⚙️ Pipeline → 3️⃣ Extract Endpoints`       | `endpoint_ids` (CSV)    |
| `📄 Files → List Files`                    | `file_name` (primer .feature) |

El **Bearer token** se añade automáticamente a todos los requests vía la pestaña *Authorization* a nivel de colección.

## 🛣️ Flujo recomendado (happy path)

```
🩺 0. Health Check
🔐 1. Auth → Login
🔑 2. Credentials → Save Jira server / email / token  (una sola vez)
📁 3. Projects → Create Project
🎫 4. Jira → POST /jira/tickets                       (lista las HUs En curso y las guarda)
🎫 4. Jira → POST /jira/tickets/{key}                 (detalle completo de la HU elegida)
⚙️ 5. Pipeline → 1️⃣ Create Execution
⚙️ 5. Pipeline → 2️⃣ Upload Postman Collection         (form-data: collection + environment)
⚙️ 5. Pipeline → 3️⃣ Extract Endpoints
⚙️ 5. Pipeline → 4️⃣ Fetch Jira Context
⚙️ 5. Pipeline → 5️⃣ List Endpoints                    (revisa cuáles van)
⚙️ 5. Pipeline → 6️⃣ Update Selection                  (opcional, ajusta selección)
⚙️ 5. Pipeline → 7️⃣ Generate                          (encola Celery)
🔌 8. WebSocket                                       (ver progreso en vivo)  o
⚙️ 5. Pipeline → 8️⃣ Get Execution                     (polling de status)
📄 6. Files → List Files                              (verifica .feature + .ts)
📄 6. Files → Download ZIP                            (proyecto listo para npm install)
```

## 📚 Carpetas y resumen

| Carpeta | Endpoints | Para qué sirve |
|---------|-----------|----------------|
| 🩺 0. Health & Docs           | `/health`, `/docs` | Sanity check del servicio |
| 🔐 1. Auth                    | `register` / `login` / `me` / `logout` | JWT (12 h) con TRL en Redis |
| 🔑 2. Credentials             | `PUT` / `GET` / `DELETE` | AES-256-GCM en BD |
| 📁 3. Projects                | CRUD básico + listado de ejecuciones | Agrupador lógico |
| 🎫 4. Jira HUs                | `POST` (lista+persiste), `GET` (catálogo BD), `POST /{key}` (detalle) | Snapshots completos de HU |
| ⚙️ 5. Pipeline de Generación  | 8 pasos secuenciales | Postman → Cypress BDD |
| 📄 6. Files & Download        | list, get, update, download ZIP | Inspección y edición manual |
| 🚨 7. Casos de Error          | 9 pruebas negativas | Verifica códigos 4xx |
| 🔌 8. WebSocket               | Instrucciones | Progreso en tiempo real |

## 🚨 Casos de error documentados

| Código | Cuándo ocurre |
|--------|---------------|
| `400` | Path traversal en `PATCH /files/{name}` · Generate sin endpoints seleccionados |
| `401` | Password incorrecto · Token inválido/expirado · Sin Authorization header |
| `403` | Path resuelto fuera del sandbox Cypress · WebSocket de otro usuario |
| `404` | Proyecto/Ejecución/Credencial inexistente o de otro usuario |
| `409` | `fetch-jira` sin `extract` previo |
| `413` | Colección Postman > 10 MB |
| `422` | Archivo subido no es `.json` · Transición de estado inválida |
| `424` | Credenciales Jira no configuradas |
| `502` | Error consultando Jira (red/credenciales inválidas/JQL malformado) |

## 🔌 WebSocket — paso a paso

Postman ≥ 10 soporta WebSockets como un tipo de request independiente:

1. **File → New → WebSocket Request**.
2. URL:
   ```
   ws://localhost:8000/ws/executions/{{execution_id}}?token={{access_token}}
   ```
3. **Connect**. Mantenlo abierto.
4. En otra pestaña ejecuta `⚙️ Pipeline → 7️⃣ Generate`.
5. Verás llegar eventos como:
   ```json
   {"type":"started","total":3}
   {"type":"file_ready","current":1,"total":3,"endpoint":"enviar notificacion Email","files":["enviar_notificacion_email.feature","enviar_notificacion_email.ts"]}
   {"type":"file_ready","current":2,"total":3, ...}
   {"type":"complete","status":"complete","total":3,"generated":3}
   ```

### Códigos de cierre WebSocket
- `4001` Unauthorized (JWT inválido)
- `4003` Forbidden (la ejecución pertenece a otro usuario)

## 🧪 Ejemplos de variantes incluidas

La carpeta **🎫 Jira HUs** trae 3 variantes del listado:

1. **Default** — tablero "En curso" del proyecto EF
2. **Only mine** — solo HUs asignadas a ti (`only_mine: true`)
3. **Tablero completo** — todas las categorías sin filtro de sprint

## 🧰 Tips

- **Encadenar pruebas:** después de `Login`, click **Run collection** (Postman Runner) y selecciona el flujo de `🔐 → 📁 → 🎫 → ⚙️` para una corrida full.
- **Refrescar token:** si recibes 401 mid-flujo, vuelve a ejecutar `Login` (el script sobrescribe `access_token`).
- **Cambiar de entorno:** duplica el environment y crea `Staging` / `Prod` apuntando a otra `baseUrl`.
- **Logs del backend:** `tail -f /tmp/uvicorn.log` mientras corres requests para ver el HTTP middleware logger.

## 🐛 Si algo falla

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| Connection refused | Backend no está arriba | `uvicorn backend.main:app --port 8000` |
| `401` después de mucho tiempo | Token expiró (12h) | Re-ejecuta `Login` |
| `424` en endpoints Jira | Credenciales sin guardar | Guarda `server` / `email` / `token` en `PUT /credentials` |
| `409` en `fetch-jira` | Saltaste el paso de extract | Ejecuta `3️⃣ Extract Endpoints` antes |
| `502` con "Error consultando Jira" | API token revocado o JQL malformado | Verifica token y prueba el JQL en Jira Cloud |
| `[]` en files tras `generate` | El worker Celery no está corriendo | `celery -A backend.tasks.celery_app worker --loglevel=info` |
