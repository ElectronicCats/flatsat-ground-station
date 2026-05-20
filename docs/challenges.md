# FlatSat CTF: Guía de Retos

Este satélite ha sido diseñado con vulnerabilidades intencionales para entrenamiento en ciberseguridad espacial. El sistema tiene 3 niveles de dificultad controlados por la variable de entorno `FLATSAT_LEVEL` en la Ground Station y por archivos de configuración en el Firmware.

## Nivel 1: Fácil (Web & Cleartext)
**Objetivo:** Comprometer la Ground Station y enviar comandos básicos al satélite.

*   **Reto 1.1: Enumeración:** Encuentra todos los endpoints de la API (`/api/endpoints`).
*   **Reto 1.2: Inyección SQL:** Extrae el hash de la contraseña del administrador desde la tabla `users` usando el buscador de telemetría.
*   **Reto 1.3: Falsificación de Sesión:** Los tokens son solo Base64. Forja un token de administrador para acceder al panel de control.
*   **Reto 1.4: Comandos en Texto Plano:** Envía el comando `TEST` al satélite a través del puente de radio.

## Nivel 2: Medio (Sistemas & CCSDS)
**Objetivo:** Explotar el sistema operativo de la Ground Station y entender el protocolo CCSDS.

*   **Reto 2.1: LFI (Local File Inclusion):** Lee archivos sensibles del sistema (como `/etc/passwd`) usando el parámetro de logs.
*   **Reto 2.2: RCE (Remote Code Execution):** Ejecuta comandos en el servidor a través del endpoint de diagnóstico.
*   **Reto 2.3: Protocolo CCSDS:** El satélite ya no acepta comandos en texto plano. Debes encapsular tus comandos en paquetes CCSDS Space Packets.

## Nivel 3: Difícil (Firmware & Criptografía)
**Objetivo:** Explotar vulnerabilidades de memoria en el firmware del satélite y romper la seguridad SDLS.

*   **Reto 3.1: Sesiones Firmadas:** Los tokens ahora están firmados con HMAC-SHA256. Necesitas la `SECRET_KEY` para forjarlos.
*   **Reto 3.2: Criptografía SDLS:** La comunicación por radio está protegida por SDLS (AES). Debes obtener las llaves o encontrar una debilidad en la implementación.
*   **Reto 3.3: Buffer Overflow:** El comando `DIAG_MEM` en el firmware es vulnerable a un desbordamiento de pila. Logra ejecutar código o causar un crash en el RP2040.

---
**Nota:** Para cambiar el nivel en la Ground Station, usa:
```bash
export FLATSAT_LEVEL=2
python webapp/wsgi.py
```
