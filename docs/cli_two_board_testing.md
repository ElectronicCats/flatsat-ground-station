# Guía de pruebas por CLI: dos FlatSat conectados

Guía práctica para verificar la transmisión por RF (uplink) entre dos placas
FlatSat usando el CLI `flatsat`. Cubre el escenario real de laboratorio: una
placa actúa como **estación terrena** (transmite) y la otra como **satélite**
(recibe).

> **Lee esto primero.** Con dos Boards conectadas, el ataque viaja **por radio**
> desde la estación terrena hasta el satélite. El `-d` que pasas es la board que
> **transmite**, no la que recibe. El NeoPixel que se enciende es el del
> **satélite**, nunca el de la estación terrena.

---

## 0. Requisitos previos

- Dos placas FlatSat conectadas por USB (VID:PID `1209:babc`).
- Permisos de acceso al puerto serie. En Linux:
  ```bash
  sudo usermod -aG dialout $USER   # cierra sesión y vuelve a entrar
  ```
- Dependencias instaladas: `pip install -r requirements.txt`

---

## 1. Descubrir las placas

```bash
flatsat devices
```

Salida esperada (los números de puerto **cambian** según how las conectes y
según el orden de enumeración USB — no te affijas):

```
                 Found 2 FlatSat device(s)
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Device              ┃ Radio 0      ┃ Radio 1      ┃ Shell (CDC2) ┃ Health  ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ [0] 503342353230000E │ /dev/ttyACM6 │ /dev/ttyACM7 │ /dev/ttyACM8 │ HEALTHY │
│ [1] 5033423532300010 │ /dev/ttyACM3 │ /dev/ttyACM4 │ /dev/ttyACM5 │ HEALTHY │
└──────────────────────┴──────────────┴──────────────┴──────────────┴─────────┘
```

**El índice `[0]` o `[1]` NO es fijo.** La lista se ordena por número de serie
USB, no por orden de conexión ni por número de `tty`. Resuelve siempre el rol
de cada placa antes de atacar:

```bash
flatsat -d 0 mode      # -> role: ground_station
flatsat -d 1 mode      # -> role: satellite
```

Anota los índices que te toquen. En el resto de esta guía asumimos:

| Índice | Rol | Qué hace |
|--------|-----|----------|
| `-d 0` | `ground_station` | **Transmite** los ataques |
| `-d 1` | `satellite` | **Recibe** y ejecuta |

> El orden puede ser inverso en tu caso. Si es así, intercambia los `-d`.

---

## 2. Comprobar la salida por downlink (Ground Station → tú)

Antes de atacar, confirma que el satélite te está enviando telemetría:

```bash
flatsat -d 0 sniff -r 0 -t 15
```

Deberías ver frames `RX:` con APID `0x001` (heartbeat) y `0x01F` (sensores),
con RSSI cercano a 0 (típicamente `-55` a `-60 dBm` a corta distancia):

```
✓ #1: TM APID=0x01F seq=0 CRC=OK (27 bytes, RSSI -60)
✓ #2: TM APID=0x001 seq=0 CRC=OK (25 bytes, RSSI -60)
✓ #3: TM APID=0x01F seq=0 CRC=OK (27 bytes, RSSI -60)
✓ #4: TM APID=0x001 seq=0 CRC=OK (25 bytes, RSSI -60)
ℹ Captured 4 frames (no --output given, nothing saved).
```

**Si no ves nada**, el problema es el downlink, no el uplink. Revisa la
configuración de radio (§7).

---

## 3. Verificar los roles y niveles

```bash
flatsat -d 0 mode          # role: ground_station
flatsat -d 1 mode          # role: satellite
flatsat -d 0 difficulty    # nivel de la GS
flatsat -d 1 difficulty    # nivel del satélite (¡el que importa!)
```

Los niveles son independientes. En un laboratorio típico verás GS en `1` y
satélite en `2`. **El nivel SDLS del satélite es el que cifra los telecommandos
reales** (`tc --protect`, `transmit --protect`). El CLI lo detecta solo
olfateando el heartbeat (§5).

---

## 4. Probar el uplink (Ground Station → Satélite)

### 4.1 El smoke test más simple

Manda un telecommando inocuo que **no** crashea ni reinicia nada y observa el
NeoPixel del **satélite**:

```bash
flatsat -d 0 attack gs-auth --yes
```

Salida esperada:

```
ℹ Target SDLS level sniffed from its downlink heartbeat: 2
ℹ Forging APID 0x12 with 'AUTH_ADMIN_OVERRIDE' XOR-encrypted under the static
  key...
✓ sent (31 bytes, TX Result: 0 (Success))
ℹ Watch the target NeoPixel: it should turn cyan (RGB 0,50,50) for ~4s, then
  fall back to its idle colour.
```

Verifica el color en la placa del **satélite** (no en la GS).

### 4.2 Interpreta el resultado

| En la salida | Significado |
|--------------|-------------|
| `✓ sent (... TX Result: 0 (Success))` | El SX126x **encoló** el paquete. **No confirma** que salió al aire. |
| `ℹ Target SDLS level sniffed ...: N` | Se detectó el nivel del satélite correctamente. |
| `⚠ Could not sniff the target's SDLS level` | No llegó ningún heartbeat; usará el nivel local. Pasa `--difficulty` a mano. |
| `✗ <error>` | El TX falló de verdad (revisa §7). |

> **Punto clave:** `TX Result: 0 (Success)` solo significa que el radio aceptó
> el paquete en su FIFO. La **única prueba real** de que el ataque llegó es el
> **cambio de color del NeoPixel del satélite**.

### 4.3 Tabla de colores esperados por escenario

Extraído del firmware (`flatsat/src/attacks/attacks.c`). El firmware lo mantiene
~4 s y luego vuelve al color idle:

| Escenario | APID | Color | RGB | Extra |
|-----------|------|-------|-----|-------|
| `apid-enum` | `0x00` | cyan suave | `0,20,20` | |
| `replay-tc` | `0x01` | azul | `0,0,50` | |
| `resetc` | `0x02` | rojo | `50,0,0` | **Reinicia el satélite** |
| `cmd-injection` | `0x04` | amarillo | `50,50,0` | |
| `gps-spoof` | `0x04` | amarillo | `50,50,0` | Reutiliza APID del thruster |
| `fuzz-crash` | `0x06` | magenta | `50,0,50` | |
| `gs-auth` | `0x12` | cyan | `0,50,50` | |
| `mem-overflow` | `0x31` | morado | `50,0,50` | Payload > 32 bytes |

> `eavesdrop` es pasivo (solo escucha) y **no** cambia ningún LED.

---

## 5. Recorrido completo de los 8 escenarios

Ejecuta uno a uno y anota el color que ves en el satélite. **Empieza por los
inocuos**; `resetc` reinicia la placa y `fuzz-crash` puede tumbar el
broadcaster.

```bash
# 00 — Enumeración de APIDs (suave; escanea un rango)
flatsat -d 0 attack apid-enum --yes
# Esperado: el escaneo ilumina APIDs válidos; al terminar, color idle.

# 01 — Eavesdropping (pasivo, no cambia LED)
flatsat -d 0 attack eavesdrop -t 10
# Esperado: frames CCSDS descifrados en pantalla.

# 02 — Fuzzing / integer underflow (APID 0x06)
flatsat -d 0 attack fuzz-crash --yes
# Esperado: magenta.

# 03 — Inyección de thruster (APID 0x04)
flatsat -d 0 attack cmd-injection --yes
# Esperado: amarillo.

# 04 — GPS spoofing (reutiliza APID 0x04)
flatsat -d 0 attack gps-spoof --yes

# 05 — Bypass de autenticación GS (APID 0x12)
flatsat -d 0 attack gs-auth --yes
# Esperado: cyan.

# 06 — Replay de telecommand (APID 0x01)
flatsat -d 0 attack replay-tc --yes
# Esperado: azul.

# 07 — Reinicio por hardware (APID 0x02) — ¡REINICIA EL SATÉLITE!
flatsat -d 0 attack resetc --yes
# Esperado: rojo y el satélite se reinicia a los ~2s.
```

### Probar con nivel explícito

Si el CLI no logra olfatear el nivel (p. ej. el satélite está apagado), fíjalo a
mano para descifrar con el nivel correcto:

```bash
flatsat -d 0 attack gs-auth --difficulty 2 --yes
```

---

## 6. Telecommands reales (no CTF)

Para el camino SDLS "legítimo" (con cifrado), usa `tc` / `transmit` con
`--protect`:

```bash
# APID 0x027 SET_DIFFICULTY, payload 0x02 -> pone el satélite en nivel 2
flatsat -d 0 tc 0x027 02 --protect

# Texto plano custom
flatsat -d 0 transmit --text "HELLO SAT" --repeat 3 --delay 1
```

Estos frames **sí** necesitan el nivel SDLS correcto del satélite, y el CLI lo
detecta automáticamente del heartbeat. Si no lo detecta, pasa
`--difficulty <0-3>`.

---

## 7. Diagnóstico: cuando el ataque "no llega"

Si el CLI dice `✓ sent` pero el NeoPixel del satélite **no cambia**, el paquete
se encoló pero el receptor no lo demoduló. Causas, en orden de probabilidad:

### 7.1 Sync word LoRa distinto (la causa más común)

El sync word debe coincidir en ambas placas. Si el transmisor está en `private`
(0x12) y el receptor en `public` (0x34), **nada llega nunca**:

```bash
flatsat -d 0 cmd 'lora_config R1'   # revisa "Sync Word:"
```

El `RadioBridge` ahora fija y restaura el sync word automáticamente en cada TX,
pero si configuraste la radio a mano y quedó inconsistente, corrígelo:

```bash
flatsat -d 0 cmd "lora_syncword R1 public"
flatsat -d 0 cmd "lora_apply R1"
```

### 7.2 Frecuencias distintas

TX y RX deben usar la misma frecuencia (uplink 916 MHz, downlink 915 MHz):

```bash
flatsat -d 0 cmd 'lora_config R0'
flatsat -d 0 cmd 'lora_config R1'
```

### 7.3 Atacaste la board equivocada

Recuerda: `-d` es **quien transmite**. Si mandaste `flatsat -d 1 attack ...`
estás transmitiendo desde el satélite (que no tiene un uplink válido hacia la GS).
Verifica los roles con `flatsat -d N mode` (§1).

### 7.4 El satélite está en bootloader

Si corriste `flatsat reboot` o la board quedó en BOOTSEL, no hay firmware
corriendo: no responde ni emite telemetría. Recover con el botón de reset /
BOOTSEL de la placa.

### 7.5 Resetear el estado del enlace

Para volver a un estado limpio tras varias pruebas:

```bash
flatsat -d 0 cmd "radio1"
flatsat -d 0 cmd "lora_syncword R1 public"
flatsat -d 0 cmd "lora_freq R1 916000000"
flatsat -d 0 cmd "lora_mode R1 command"
flatsat -d 0 cmd "lora_apply R1"
```

---

## 8. Verificación por script (automatizada)

Para una comprobación reproducible sin.color, usa el script de referencia que
manda un SET_DIFFICULTY y lee el nivel resultante del satélite:

```bash
python3 - <<'PY'
import sys, time
sys.path.insert(0, ".")
from modules.core.ccsds import build_tc, sdls_protect_frame
from modules.core.constants import APID_TC_SET_DIFFICULTY
from modules.core.device import FlatSatDevice
from modules.core.radio_bridge import RadioBridge
from modules.core.serial_manager import discover_devices
from modules.core.state import GroundStationState

objs = {}
for d in discover_devices():
    dev = FlatSatDevice(d); dev.connect()
    objs[d.identity.serial_number] = dev
    print(d.identity.serial_number, dev.send_shell_command_full("mode"))

gs  = next(v for v in objs.values() if "ground_station" in (v.send_shell_command_full("mode") or ""))
sat = next(v for v in objs.values() if "satellite" in (v.send_shell_command_full("mode") or ""))

def diff(board):
    r = board.send_shell_command_full("difficulty") or ""
    return int([t for t in r.split() if t.isdigit()][0])

def tx(frame):
    st = GroundStationState(); st.set_hardware(gs); st.difficulty = 1
    return RadioBridge(st).send_raw(frame)

print("satellite BEFORE =", diff(sat))
tx(sdls_protect_frame(build_tc(APID_TC_SET_DIFFICULTY, b"\x00", seq_count=1,
                               timestamp=int(time.time())), 2))
time.sleep(1.2)
print("satellite AFTER  =", diff(sat), "(0 = el uplink funcionó)")

tx(build_tc(APID_TC_SET_DIFFICULTY, b"\x02", seq_count=2, timestamp=int(time.time())))
time.sleep(1.2)
print("restored         =", diff(sat))
for d in objs.values(): d.disconnect()
PY
```

Si `BEFORE` y `AFTER` son distintos (o el frame se acepta y el nivel cambia), el
uplink funciona. Si `AFTER` no cambia, vuelve a §7.

---

## 9. Ejecutar los tests automatizados

```bash
python3 -m pytest tests/ -q            # suite completa
python3 -m pytest tests/test_rf_uplink_fixes.py -v   # regressions del uplink
```

Los tests de esta guía cubren: sync word antes/después del TX, sync word
restaurado, frames CTF en claro (no SDLS), detección de nivel por heartbeat,
`-d` en el grupo `attack`, y que un fallo de revert no oculte un TX exitoso.

---

## 10. Si el satélite no responde por USB pero sí transmite

Un síntoma que puede confundir: el CLI informa `HEALTHY` en `flatsat devices`
porque los puertos USB existen, pero `flatsat -d 1 mode` devuelve
`(no response)`. Si el heartbeat sigue llegando por RF (§2), **el satélite
está vivo y transmittiendo** — lo que falla es su shell por USB.

Comprueba si es tu caso:

```bash
flatsat -d 0 sniff -r 0 -t 8      # ¿llega telemetría del satélite?
```

Si llegan frames `APID=0x001` (heartbeat) pero el shell del satélite no
responde, el enlace RF está bien y el problema es local a la placa:

1. Reinicia el satélite (desenchúfala y vuélvela a enchufar). Un `resetc` o un
   `flatsat reboot` previos pueden haberla dejado colgada.
2. Si sigue igual, su shell quedó en un estado inconsistente: no hay comando
   remoto para forzar un reinicio por RF, hace falta intervención física.
3. Mientras tanto **puedes seguir probando los ataques**: solo necesitas la GS
   (§4 y §5), porque la evidencia de llegada es el NeoPixel del satélite, no su
   shell.

---

## Resumen rápido

```bash
flatsat devices                        # 1. descubrir placas y roles
flatsat -d 0 sniff -r 0 -t 10          # 2. confirmar downlink
flatsat -d 0 attack gs-auth --yes      # 3. smoke test del uplink
                                       #    -> satellite NeoPixel: cyan
# luego recorre los 8 escenarios de §5
```