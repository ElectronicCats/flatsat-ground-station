#!/bin/sh
set -e

# ──────────────────────────────────────────────────────────────────────────────
# PwnSat2 Ground Station — Docker Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

# Fix host volume mount permissions recursively for /app/db if owned by root/host user
mkdir -p /app/db 2>/dev/null || true
chown -R appuser:appuser /app/db 2>/dev/null || true
chmod -R 777 /app/db 2>/dev/null || true


# Drop root privileges and execute application as non-root appuser
exec gosu appuser "$@"
