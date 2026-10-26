# Probar el CLI — FlatSat Ground Station

Checklist para comprobar que la CLI funciona, con y sin la webapp conectada.

---

## 1. Dos modos de uso

| Modo | Cuándo | Comando |
|---|---|---|
| **Directo** | La webapp **no** tiene la placa | `flatsat status` |
| **Vía webapp** (`-w`) | La webapp **sí** tiene la placa | `flatsat -w status` |

El modo directo abre los puertos serie. El modo `-w` habla con la API REST de
la webapp, que es quien tiene el hardware. **No se pueden usar a la vez**:
en Windows los puertos CDC-ACM son de acceso exclusivo.

---

## 2. Antes de empezar: ¿hay algún proceso con la placa?

```bash
flatsat devices
```

Si la placa aparece como `HEALTHY` con sus tres puertos, sigue con el §3.
Si dice *"No FlatSat devices detected"*, revisa el §6.

> **Truco**: si un comando falla con
> `✗ Failed to open Shell serial interface`, casi siempre es que **otro
> proceso tiene los puertos abiertos** (típicamente la webapp). Ciérrala o usa
> el modo `-w`.

---

## 3. Checklist del CLI (modo directo)

```bash
flatsat --help              # lista de comandos (o 'flatsat help')
flatsat version             # versión instalada
flatsat devices             # placa y sus 3 endpoints (Radio0/Radio1/Shell)
flatsat status              # firmware, modo, estado del radio
flatsat mode                # role actual de la placa
flatsat flight              # estado de vuelo (idle/nominal/safe/debug)
flatsat difficulty          # nivel de seguridad SDLS (0-3)
flatsat sensors             # sensores en vivo (BME280 + LIS2DH)
flatsat sniff -n 3 -t 15    # captura 3 tramas CCSDS en 15 s
flatsat sniff -n 3 -o cap.json   # ... y las guarda a un JSON
flatsat cmd status          # comando shell crudo
flatsat install             # instala la app (CLI en el PATH, accesos directos)
flatsat uninstall           # la desinstala
```

Salida esperada de `flatsat status` con la placa conectada:

```
SYSTEM STATUS
FW: dev-3aa4142-dirty
Git: 3aa4142 (dirty)
Built: 2026-10-06T17:46:47Z
Compiler: GNU 12.2.0
Flat-Sat FW: dev-3aa4142-dirty  Active Radio: 0 (TX: 1, RX: 0)
  RadioManager State: LISTENING
  Radio0: LoRa  mode=stream  lora_init=1  fsk_init=0  (Ready)
  Radio1: LoRa  mode=stream  lora_init=1  fsk_init=0  (Ready)
```

Y de `flatsat sniff`:

```
✓ #1: TM APID=0x01F seq=0 CRC=OK (27 bytes, RSSI -20)
✓ #2: TM APID=0x001 seq=0 CRC=OK (25 bytes, RSSI -20)
```

---

## 4. Probar el CLI con la webapp conectada

**¿En qué terminal? En cualquiera.** `-w` es solo un cliente HTTP: da igual
que sea cmd, PowerShell, la Terminal de macOS o bash. Lo único que importa es
que la webapp esté corriendo en *algún* sitio y que el terminal tenga el
comando `flatsat` disponible.

### La webapp en segundo plano (misma terminal)

Si quieres la webapp y la CLI **en la misma terminal**, arranca la webapp en
segundo plano:

```bash
flatsat-web --background
```

```
[+] WebApp en segundo plano: http://127.0.0.1:5000
    Log: ...\FlatSatGroundStation\bin\flatsat-web.log

    Usa 'flatsat -w <comando>' para hablar con ella desde esta misma terminal.
    Para pararla:  taskkill /IM flatsat-web.exe /F
```

El prompt vuelve immediately y ya puedes usar la CLI:

```bash
flatsat -w status
flatsat -w sniff -n 3 -t 15
```

En macOS/Linux, para pararla: `pkill -f flatsat-web`.

### La webapp en primer plano (dos terminales)

```
TERMINAL A (o doble clic en el menú Inicio)
─────────────────────────────────────────
    flatsat-web
    → dashboard en http://127.0.0.1:5000
    → en el dashboard: Scan → Connect con tu placa

TERMINAL B (cmd, PowerShell, Terminal, bash…)
─────────────────────────────────────────────
    flatsat -w status
    flatsat -w sniff -n 3 -t 15
```

Formas de invocarlo (todas equivalentes):

```bash
flatsat -w status                        # la webapp local (127.0.0.1:5000)
flatsat status -w                        # lo mismo, el flag detrás
flatsat status --web-url http://ip:5000  # otra webapp
flatsat -w --web-url http://ip:5000 status
```

> `-w` es un **flag**, no una opción con valor: así nunca se come el nombre
> del comando (`flatsat -w status` funciona, no `flatsat -w=status`).

Si la webapp no está en el puerto 5000 (en macOS el 5000 lo usa AirPlay),
arráncala con otro puerto y apúntala:

```bash
flatsat-web --port 5001                                  # terminal A
flatsat -w --web-url http://127.0.0.1:5001 status        # terminal B
```

---

## 5. Los comandos de ataque (CTF)

```bash
flatsat attack --help              # lista de escenarios
flatsat attack resetc --yes        # reboot por hardware sin autenticar
flatsat attack flood --help
```

Requieren que la placa esté en el nivel de dificultad correcto
(`flatsat difficulty 0|1|2|3`).

---

## 6. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `No FlatSat devices detected` | Placa no conectada o sin permisos | `flatsat-gs doctor`; en Linux, `sudo usermod -aG dialout $USER` |
| `Failed to open Shell serial interface` | Otro proceso tiene los puertos | Cierra la webapp o usa `-w` |
| `sniff` no captura nada | El radio no recibe (o está en TX) | `flatsat status` y mira `Active Radio` / `RadioManager State` |
| `sniff` dice *"No CCSDS frames captured"* | Frames que no son CCSDS, o CRC inválido | Mira el log de la webapp: `[RADIO0 CRC] bad CRC` |
| Los logs no salen en un fichero | Buffering de stdout | Arranca con `python -u flatsat_app.py web` |
| `flatsat` no se encuentra | La terminal heredó un entorno antiguo | En Windows los lanzadores de `%LOCALAPPDATA%\Microsoft\WindowsApps` lo resuelven sin reiniciar; si sigue sin aparecer, abre la terminal desde el menú Inicio |
| `flatsat` no se encuentra (Linux/macOS) | `~/.local/bin` no está en el PATH de la shell | `export PATH="$HOME/.local/bin:$PATH"` o abre una terminal nueva |

---

## 7. Instalar / desinstalar la CLI

```bash
flatsat-gs install      # pone flatsat, flatsat-web y flatsat-gs en el PATH
flatsat-gs uninstall    # los quita, restaura el PATH y borra los alias
```

Tras instalar, `flatsat` funciona igual en cmd, PowerShell, Terminal (macOS)
y bash/zsh (Linux). En PowerShell se comprueba con:

```powershell
(Get-Command flatsat).Source
```

Debe devolver la ruta del `.exe` instalado, no el nombre de una función.

---

## 8. Ejecutar la CLI sin instalar nada

Desde el repositorio, con un Python que tenga las dependencias:

```bash
python flatsat.py devices
python flatsat.py status
```

O con el lanzador que busca el Python correcto (Windows):

```bat
run.cmd cli devices
```
