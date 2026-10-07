#!/bin/sh
set -e

# ──────────────────────────────────────────────────────────────────────────────
# PwnSat2 Ground Station — Docker Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

# Fix host volume mount permissions recursively for /app/db if owned by root/host user
mkdir -p /app/db 2>/dev/null || true
chown -R appuser:appuser /app/db 2>/dev/null || true
chmod -R 777 /app/db 2>/dev/null || true

# ──────────────────────────────────────────────────────────────────────────────
# Permisos de los puertos serie USB (FlatSat / CatSniffer)
#
# Los nodos /dev/ttyACM* / /dev/ttyUSB* se crean en el contenedor con modo 0600
# y propietario root:root (así los deja runc al mapearlos con `devices:`), por lo
# que el usuario sin privilegios 'appuser' no puede abrirlos y el escaneo de
# hardware falla con "Permission denied".
#
# Se abren a root:dialout con 0660 (rw para root y dialout, nada para el resto).
# El grupo dialout ya está asignado a appuser en el Dockerfile.
# ──────────────────────────────────────────────────────────────────────────────
for dev in /dev/ttyACM* /dev/ttyUSB*; do
    [ -e "$dev" ] || continue
    chgrp dialout "$dev" 2>/dev/null || true
    chmod 0660 "$dev" 2>/dev/null || true
done


# Drop root privileges and execute application as non-root appuser
exec gosu appuser "$@"
