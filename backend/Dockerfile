FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend y el core reutilizable (app/).
# El código importa tanto `backend.*` como `app.*`; con PYTHONPATH=/app ambos
# paquetes resuelven sin symlinks. `backend/core/` (constants/state_machine) es
# un paquete real propio del backend y NO debe colisionar con app/.
COPY backend/ ./backend/
COPY app/ ./app/

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
