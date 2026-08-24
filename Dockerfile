# ──────────────────────────────────────────────────────────────────────────────
# PwnSat2 Ground Station — Dockerfile
# ──────────────────────────────────────────────────────────────────────────────
# Build:  docker build -t flatsat-gs .
# Run:    docker compose up
# ──────────────────────────────────────────────────────────────────────────────

# 1. Base: Python 3.11 slim (Debian Bookworm)
FROM python:3.11-slim

# 2. Evitar prompts interactivos durante el build
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLATSAT_LEVEL=3 \
    FLATSAT_PORT=5000 \
    FLATSAT_DEBUG=0


WORKDIR /app

# 3. Dependencias de sistema:
#    - libudev-dev  → pyudev (detección de dispositivos USB/serial)
#    - udev         → reglas de dispositivo dentro del contenedor
#    - libusb-1.0-0 → acceso USB de bajo nivel
#    - libpq-dev / build-essential → compilar extensiones C de las dependencias
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libudev-dev \
        libusb-1.0-0 \
        udev \
        gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Instalar dependencias Python (cacheadas si requirements.txt no cambia)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar código fuente
COPY . .

# 6. Crear directorio de base de datos con permisos correctos
RUN mkdir -p /app/db && chmod 777 /app/db

# 7. Usuario no-root para mayor seguridad
#    (el grupo 'dialout' es necesario para acceder a /dev/ttyACM*)
RUN groupadd -r appuser && \
    useradd -r -g appuser -G dialout appuser && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appuser /app


# 8. Puerto de la webapp
EXPOSE 5000

# 9. Health check — verifica que el servidor responde
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; p=os.environ.get('FLATSAT_PORT','5000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/login')" || exit 1


# 10. Entrypoint y comando por defecto para ejecutar la webapp
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "webapp.app"]

