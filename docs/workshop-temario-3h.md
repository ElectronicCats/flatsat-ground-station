# Temario Taller FlatSat — versión 3 h (`Taller_FlatSat.pptx`)

> Fuente: `Taller_FlatSat.pptx` (extraído a texto en `Taller_FlatSat.pptx.txt`).
> Workshop original de **8 h** (9 bloques, 132 diapositivas) reducido a **3 h máximo**.
> Formato: `Conferencia Unknown · Perú · 8 h · presencial` → propuesta `3 h · presencial o remoto`.

---

## 1. Temario original (8 h)

| # | Bloque | Min | Diapositivas |
|---|--------|-----|--------------|
| 0 | Introducción y logística (registro, setup, reglas) | 30 | 5–10 |
| 1 | Qué es FlatSat y su arquitectura | 40 | 11–18 |
| 2 | Teoría de base: RF, espectro, LoRa y antenas | 60 | 19–32 |
| 3 | Hardware: radios, sensores y puntos de prueba | *(junto con 2)* | 33–43 |
| 4 | CCSDS / Space Packet Protocol | 55 | 44–57 |
| 5 | Carga de firmware (UF2) y validación de enlace | 45 | 58–72 |
| 6 | Captura de paquetes con CatSniffer | 60 | 73–91 |
| 7 | Seguridad: modelo de amenazas y vectores | 45 | 92–101 |
| 8 | Ejercicios de ataque y defensa (USB + RF) | 90 | 102–127 |
| 9/CIERRE | Reto integrador (CTF) y preguntas | 55 | 128–131 |

**Total contenido lectivo: ~480 min (8 h)** + pausa 15 min + comida 45 min.

---

## 2. Criterios de reducción (8 h → 3 h)

- **180 min netos totales.** Todo lo que no sea *imprescindible para capturar y atacar*
  se condensa a 1 diapositiva o se mueve a material de apoyo (anexo).
- Queda **igual de práctica**: la reducción es de teoría, no de manos a la obra.
  El 60%+ del tiempo sigue siendo manipulación real (CLI, sniffing, inyección USB/RF, CTF).
- Se recorta en este orden de prioridad:
  1. Teoría de RF «de libro» (espectro EM, modulación, link budget, antenas, impedancia) → anexo.
  2. Detalles internos de los scripts (código Python, explicación de las rutinas de captura) → anexo.
  3. Hardware de bajo impacto para el ejercicio (puntos de prueba SWD, BUTTONs, buses) → 1 lámina.
  4. Los 6 vectores de ataque se presentan en 2–3 láminas en lugar de una por vector.
- Setup previo exigido al alumno: repositorio clonado, `.venv` y alias `flatsat` funcionando
  **antes** de la sesión (se revisa en los primeros 5 min, no se enseña desde cero).

---

## 3. Agenda propuesta (3 h)

| Hora | Bloque | Min | Qué se cubre |
|------|--------|-----|--------------|
| 00:00 | Bienvenida + logística exprés | 10 | Presentadores (1 lámina), reglas/ética, verificación de setup (clone + `.venv` + `flatsat --help`) |
| 00:10 | FlatSat + lo mínimo de RF + hardware | 20 | Qué es, «vulnerable a propósito», flujo TM/TC (1 lámina), uplink/downlink, LoRa SF/BW/CR, 2× SX1262, sensores, 3 endpoints USB |
| 00:30 | CCSDS / SPP esencial | 20 | TM vs TC, Primary Header de 6 bytes, APID, mapa de telecomandos, formato de telemetría (BME280/LIS2DH/heartbeat) |
| 00:50 | Carga de firmware y validación | 20 | UF2 (drag & drop), comandos CLI de diagnóstico y misión, sintonía de antenas (un escenario, loopback o 2 tarjetas) |
| 01:10 | Captura y análisis (CatSniffer / CLI) | 30 | Estación terrena, configurar el receptor, `sniff`/`replay_capture`, decodificar APID, reconstruir telemetría |
| 01:40 | Seguridad: amenazas y vectores | 15 | STRIDE resumido + 6 vectores en 1 lámina de resumen |
| 01:55 | Ataque y defensa en la práctica | 40 | Checkpoint PING, Ruta A (USB) y Ruta B (RF), spoofing (SAFE), tampering, logic bomb, replay, mitigaciones |
| 02:35 | Reto integrador (CTF) | 15 | 4 banderas: downlink, APID oculto, telemetría falsa, logic bomb |
| 02:50 | Evaluación rápida + cierre | 10 | 5 preguntas (o 3) + gracias |

**Total: 180 min** (sin pausa larga; sugerir 2 descansos de 5–10 min opcionales → 3 h 20).

### Distribución teoría/práctica

| Componente | Min | % |
|-----------|-----|---|
| Teoría/demo exprés | 65 | 36% |
| Práctica guiada (CLI + ataques) | 100 | 56% |
| CTF + cierre | 25 | 14% |

---

## 4. Mapa de recorte por bloque (láminas a conservar)

La numeración sigue `Taller_FlatSat.pptx.txt`. **CONS** = conservar tal cual, **1-LAM** = condensar a una sola lámina, **ANEXO** = mover a material de apoyo, **ELIM** = eliminar.

### Bloque 0 (5–10)
| Lámina | Trato | Nota |
|--------|-------|------|
| 1–4 (título, bienvenida, bios) | 1-LAM | Bios de Eduardo y Andrés en una sola lámina |
| 6 (lo que vamos a ver) | CONS | Actualizar a 3 h |
| 7 (agenda 8 h) | 1-LAM | Reemplazar por agenda 3 h |
| 8 (reglas, ética) | CONS | Imprescindible |
| 9–10 (setup CLI, alias) | 1-LAM | Entregar como prerequisito; solo verificar |

### Bloque 1 (11–18)
| Lámina | Trato | Nota |
|--------|-------|------|
| 13 (qué es FlatSat) | CONS | |
| 14 (vulnerable a propósito) | CONS | |
| 15 (ciberseguridad espacial) | 1-LAM | Fusionar con 13/14 |
| 16 (analogía satélite real) | CONS | |
| 17–18 (flujo TM / flujo TC) | 1-LAM | Un solo diagrama up/downlink |

### Bloque 2 (19–32) — el mayor recorte
| Lámina | Trato | Nota |
|--------|-------|------|
| 26 (uplink y downlink) | CONS | Núcleo para cualquier ataque |
| 28 (qué es LoRa) | CONS | Breve |
| 29 (SF, BW, CR) | CONS | Esencial para sintonía |
| 24 (potencia y sensibilidad) | 1-LAM | |
| 21–23, 25, 27, 30–32 (onda EM, espectro, modulación, link budget, antenas, impedancia) | ANEXO | Teoría de consulta; no bloquea el taller |

### Bloque 3 (33–43)
| Lámina | Trato | Nota |
|--------|-------|------|
| 35 (componentes principales) | CONS | |
| 36–37 (dos radios SX1262) | 1-LAM | Unir la explicación de R0/R1 |
| 39 (sensores: telemetría) | CONS | |
| 43 (tres endpoints USB) | CONS | Clave para entender Ruta A |
| 38 (RP2040), 40 (indicadores), 41 (buses), 42 (puntos de prueba) | 1-LAM | Una sola lámina «el resto del hardware» |

### Bloque 4 (44–57)
| Lámina | Trato | Nota |
|--------|-------|------|
| 46 (qué es CCSDS) | CONS | |
| 48 (TM vs TC) | CONS | |
| 49 (Primary Header 6 bytes) | CONS | Núcleo del taller |
| 50 (Packet Identification) | CONS | |
| 51 (Packet Sequence Control) | 1-LAM | Pegar nota «anti-replay» aquí |
| 52 (Packet Length) | 1-LAM | Fusionar con 49 |
| 53 (APIDs) | CONS | |
| 54–55 (mapa de telecomandos) | 1-LAM | Un solo mapa; el resto al anexo |
| 56 (formato de telemetría) | CONS | Con formato BME280/LIS2DH/heartbeat |
| 47 (SANA, libros CCSDS) | ANEXO | |
| 57 (bytes crudos por RF) | 1-LAM | Nota dentro de 49 |

### Bloque 5 (58–72)
| Lámina | Trato | Nota |
|--------|-------|------|
| 60 (qué es UF2) | CONS | |
| 61–62 (bootloader + drag&drop) | 1-LAM | Un solo flujo visual |
| 65 (comandos de diagnóstico) | CONS | |
| 66 (comandos de configuración de misión) | CONS | |
| 69–72 (sintonía de antenas, casos A/B/C) | 1-LAM | Un solo escenario demo (loopback 1 tarjeta o 2 tarjetas); el resto al anexo |
| 63 (eliminación minicom/PuTTY) | ELIM | Nota dentro de 65 |
| 64 (instalación CLI) | ELIM | Prerequisito |
| 67 (validar por consola) | 1-LAM | Fusionar con 65 |
| 68 (troubleshooting) | ANEXO | Entregar como cheat sheet |

### Bloque 6 (73–91)
| Lámina | Trato | Nota |
|--------|-------|------|
| 75 (qué es una estación terrena) | 1-LAM | Con 76 (CatSniffer) |
| 76 (CatSniffer como GS) | CONS | |
| 77 (configurar CatSniffer) | CONS | Parámetros exactos |
| 79–80 (Ataque 1: Sniffing) | 1-LAM | Proceso + definición juntos |
| 81 (ejecutar el ataque) | CONS | Comandos por OS |
| 90 (reconstruir telemetría / hijacking) | CONS | Con `ccsds_tools.py parse` |
| 87–88 (qué hace exactamente + bit a bit) | 1-LAM | Ejemplo de decodificación en vivo |
| 89 (decodificar header a mano) | 1-LAM | Fusionar con 87–88 |
| 91 (forge_command.py) | CONS | Presenta Ruta A/B |
| 82–86 (internos del script, código serie/CCSDS/CRC) | ANEXO | Código Python de referencia |

### Bloque 7 (92–101)
| Lámina | Trato | Nota |
|--------|-------|------|
| 94 (STRIDE) | 1-LAM | Resumen compacto |
| 95 (¿por qué son vulnerables?) | 1-LAM | Breve |
| 96–101 (6 vectores) | 1-LAM | Tabla: vector → qué es → ejemplo. Cada uno se demuestra en el Bloque 8 |

### Bloque 8 (102–127) — el bloque «hígado»
| Lámina | Trato | Nota |
|--------|-------|------|
| 105 (dos rutas, un mismo paquete) | CONS | |
| 106 (Ruta A USB) | CONS | |
| 107 (Ruta B RF) | CONS | |
| 115 (checkpoint: el PING manda) | CONS | Regla de oro |
| 113 (qué hace exactamente el forjado) | 1-LAM | Con 110–112 |
| 114 (guía paso a paso SAFE) | CONS | Demo de spoofing |
| 116 (APID brute-force) | CONS | Ejercicio rápido |
| 117 (telemetry tampering) | CONS | |
| 118 (logic bombing) | CONS | |
| 125 (qué hace exactamente: replay) | CONS | |
| 126 (defensa: mitigaciones) | CONS | Cierra el círculo |
| 127 (ataque → mitigación) | CONS | Tabla resumen |
| 104 (construcción con ccsds_tools.py) | 1-LAM | Con 113 |
| 108–109, 110, 111, 112 | ANEXO/1-LAM | Detalles script e intro spoofing |
| 119–124 (replay teoría + código) | 1-LAM | Teoría anti-replay + ejecución; código al anexo |

### Cierre (128–131)
| Lámina | Trato | Nota |
|--------|-------|------|
| 129 (retos integrador CTF) | CONS | 4 banderas |
| 130 (evaluación rápida) | 1-LAM | Quitar a 3 preguntas o quiz en vivo |
| 131 (gracias) | CONS | |

**Resultado estimado:** de **132 láminas → ~60–65 láminas** (55% de recorte de material
teórico/de consulta, 100% de práctica conservada).

---

## 5. Pendientes de contenido (revisar en el deck)

1. **Frecuencias inconsistentes:** el deck mezcla downlink 915/916 MHz y uplink 916/918 MHz
   según la lámina (17, 26, 77, 79, 107, 109, 114, 119…). Uniformar una sola pareja
   (recomendado: uplink 918 / downlink 916, que es la usada en los ejercicios y en el README).
2. **Baudios:** la lámina 68 menciona 921600 baud y el resto del deck 115200. Unificar.
3. **Comando `flatsat cmd --interactive`:** la lámina 67 usa una opción que no existe en el CLI
   actual (ver `cli/commands/cmd.py`); el comando real es `flatsat console`.

---

## 6. Material de apoyo (para lo que se movió a ANEXO)

- Teoría de RF: onda EM, espectro, modulación, link budget, antenas e impedancia (lam 21–25, 27, 30–32).
- SANA y códigos de color de libros CCSDS (lam 47).
- Código fuente comentado de captura, decodificación y CRC (lam 82–86).
- Troubleshooting de carga de firmware (lam 68).
- Escenarios de sintonía de antenas B y C (lam 70–72).
- Detalles internos de `forge_command.py` y `replay_capture.py` (lam 104, 108–112, 119–124).