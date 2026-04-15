# Release Prep: Webapp Ground Station

**Date:** 2026-04-14
**Deadline:** 2026-04-16
**Target:** v0.1.0-beta — plug-and-play para taller CTF con FlatSat hardware

## Context

La webapp ground station (Flask + SocketIO) está funcionalmente completa: 12/12 flags GS, 189 tests, core library estable. Necesita pulirse para que cualquier instructor pueda clonar, instalar y correr sin fricción, y opcionalmente usar Docker.

## Scope

### In scope

1. **Auditoría de primer uso** — clonar fresco, detectar fricciones en el flujo de arranque
2. **Pinear dependencias** — `requirements.txt` con versiones exactas
3. **Flujo de arranque sin fricciones** — `python -m webapp.app` debe: crear DB si no existe, seed si está vacía, arrancar en modo simulado si no hay hardware. Sin pasos manuales.
4. **Revisar `.gitignore`** — DBs con datos, caches, `.env`, etc.
5. **README actualizado** — requisitos, instalación, arranque, credenciales, troubleshooting
6. **Dockerfile + docker-compose.yml** — imagen ligera, USB passthrough para FlatSat
7. **Tag v0.1.0-beta**

### Out of scope

- Refactor a Flask Blueprints
- Contenido CTF (challenges, guías, narrativas)
- CI/CD pipelines
- Changelog formal
- Tests nuevos (los 189 existentes cubren la funcionalidad)

## Design decisions

- **Sin `.env` file** — las credenciales default son intencionales (CTF), las crypto keys son parte del ejercicio. No hay secretos reales que proteger.
- **DB auto-init** — SQLite se crea en `db/` al arrancar si no existe. Seed idempotente.
- **Modo simulado como fallback** — si no detecta FlatSat USB, arranca en SIMULATED sin error.
- **Docker con `--device`** — passthrough USB al container, no privileged mode completo.
- **Python 3.11+ requerido** — ya está en el README, mantenerlo.
