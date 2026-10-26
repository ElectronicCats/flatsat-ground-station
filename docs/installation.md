# Guía de instalación — FlatSat Ground Station

Guía completa para instalar la aplicación (dashboard web + CLI) en Windows, Linux
y macOS **sin Docker y sin máquina virtual**, y para desinstalarla limpiando.

---

## 1. Qué se instala

| Elemento | Detalle |
|---|---|
| Dashboard web | Flask + WebSocket, telemetría en vivo, panel de control de la placa |
| CLI | `flatsat` — shell interactivo con 20+ comandos (devices, status, sniff, tc, attack…) |
| Diagnóstico | `flatsat-gs doctor` — lista puertos serie y dice qué bloquea el hardware |
| Dependencias | 7 paquetes: Flask, Flask-SocketIO, simple-websocket, click, rich, pyserial, pycryptodome |

Todas tienen ruedas precompiladas: **no hace falta compilador ni `build-essential`**.

---

## 2. Un solo instalador, un solo binario

FlatSat Ground Station tiene **un único instalador** y **un único binario**.
Todos los demás caminos son atajos que delegan en él:

```
                    ┌─────────────────────────────┐
                    │  flatsat_app.py install      │  ← el instalador real
                    │  (o "flatsat-gs install")     │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
       flatsat-gs install                        run.cmd install
       (binario autónomo)                        (Windows: busca Python)
```

No hay más instaladores: ni scripts de Setup, ni instaladores de sistema.
El binario **se instala a sí mismo**.

**Qué instala, siempre igual:**

| | |
|---|---|
| Ejecutables | `flatsat-gs` (app), `flatsat-web` (dashboard), `flatsat` (CLI) |
| Dónde | `%LOCALAPPDATA%\Programs\FlatSatGroundStation` (Windows) · `~/.local/share/flatsat-ground-station` (POSIX) |
| Accesos directos | Menú Inicio (Windows) · `~/.local/share/applications` (Linux) |
| PATH | Se añade el directorio de binarios y **se restaura al desinstalar** |
| Alias de shell | Se eliminan al instalar y al desinstalar |
| Desinstalación | `flatsat-gs uninstall` — borra todo y restaura el PATH |

### ⚠️ Antes de nada (Windows)

Si al abrir una terminal te sale esto:

```
Python was not found; run without arguments to install from the Microsoft Store...
```

es que el alias de Microsoft Store está tapando tu Python real. **No pasa
nada**: usa `py` en lugar de `python`, o directamente el lanzador incluido:

```bat
run.cmd                  :: dashboard web
run.cmd cli              :: CLI
run.cmd install          :: instalar en el perfil del usuario
```

`run.cmd` busca el primer Python que funcione (comprueba de verdad que
ejecute código, no solo que exista) y lanza la aplicación.

Para quitar el alias de forma permanente:
*Ajustes → Aplicaciones → Alias de ejecución de la aplicación → desactiva
`python.exe` y `python3.exe`*.

---

### Método A — Binario autónomo (cero instalación) ★ recomendado para asistentes

No necesitas Python. Es **un único fichero** con Python, Flask, pyserial,
click y todo lo demás dentro. El mismo binario serves para el dashboard y
para el CLI.

**Dónde conseguirlo:**

| Origen | Cuándo |
|---|---|
| `dist\flatsat-gs.exe` (Windows) | Compilado en este repositorio, en la carpeta `dist/` |
| `dist/flatsat-gs` (Linux/macOS) | Idem |
| GitHub Releases | Cuando se publiquen los assets de la release |

> La carpeta `dist/` está en `.gitignore` (es un artefacto de compilación),
> así que **no viaja en el `git clone`**. Si no lo tienes, compílalo:
>
> ```bat
> REM Windows
> .
un.cmd build
> ```
> ```bash
> # Linux / macOS
> ./compile_app.sh
> ```

Uso:

```bash
# Windows
dist\flatsat-gs.exe

# Linux / macOS
chmod +x dist/flatsat-gs
./dist/flatsat-gs
```

Se abre el dashboard en <http://127.0.0.1:5000>.

**Para dejarlo instalado en el equipo** (crea ejecutables reales en el PATH,
sin permisos de administrador):

```bash
dist\flatsat-gs.exe install
```

La instalación crea **tres ejecutables de verdad** —no scripts— que comparten
el mismo fichero (en Windows son *hard links*, así que ocupan 20 MB en total,
no 60):

| Ejecutable | Qué hace al abrirlo |
|---|---|
| `flatsat-gs.exe` | La aplicación completa: dashboard + CLI + diagnóstico |
| `flatsat-web.exe` | El dashboard web directamente |
| `flatsat.exe` | El CLI interactivo directamente |

Además se crean accesos directos en el menú Inicio con el icono de la
aplicación.

> Cada ejecutable se comporta según el nombre con el que se invoca, así que
> los tres son el mismo programa.

---

### Método B — Desde el repositorio (un comando)

Necesitas Python 3.9 o superior.

```bash
git clone https://github.com/ElectronicCats/flatsat-ground-station.git
cd flatsat-ground-station

python flatsat_app.py          # Linux / macOS
py flatsat_app.py              # Windows (si "python" abre la Microsoft Store)
run.cmd                        # Windows: detecta el Python correcto solo
```

La primera ejecución comprueba qué falta, crea un entorno virtual local
(`.venv`), instala las 7 dependencias y arranca. Las siguientes reutilizan ese
entorno: **solo se instala una vez**.

> ¿Prefieres instalarlo de una vez para que el comando `flatsat` quede
> disponible en cualquier terminal? Usa el **Método C** (abajo) o simply
> lanza el binario autónomo, que se instala solo.

Los tres lanzadores son equivalentes:

```bash
python flatsat_app.py          # dashboard web
python flatsat.py              # CLI
run.cmd                        # Windows: cualquiera de los dos
```

> **Para probar la instalación desde cero**: si el repositorio ya tiene un
> `.venv` con las dependencias, el arranque es instantáneo y no se ve el
> bootstrap. Bórralo (`rm -rf .venv`) o usa otro intérprete para ver el
> proceso completo de instalación.

---

### Método C — Instalación permanente dentro del proyecto

Es el instalador de verdad. Lo que uses para llegar hasta aquí (el binario
o `run.cmd`) acaba aquí:

```bash
flatsat-gs install          # si tienes el binario
python flatsat_app.py install   # si lo ejecutas desde el repositorio
```

La instalación vive **dentro de la carpeta del proyecto**, en `flatsat-gs/`:

```
flatsat-ground-station/
├── flatsat-gs/                     ← la instalación
│   ├── bin/                        ← flatsat-gs, flatsat-web, flatsat
│   ├── db/                         ← base de datos de telemetría
│   ├── venv/                       ← entorno virtual de la app
│   └── install-manifest.json       ← qué se creó (para desinstalar)
├── modules/  webapp/  tools/ ...
```

Así todo (código, ejecutables, datos y logs) está en un único sitio: se
puede copiar a otro equipo, mover o borrar con un solo comando.

| Sistema | Dónde se instala |
|---|---|
| Windows | `<proyecto>\flatsat-gs` |
| Linux / macOS | `<proyecto>/flatsat-gs` (+ enlaces en `~/.local/bin`) |

En Windows la carpeta `flatsat-gs\bin` se añade al PATH del usuario y se
dejan unos lanzadores en `%LOCALAPPDATA%\Microsoft\WindowsApps` para que los
comandos funcionen incluso en terminales ya abiertas.

Para instalar en otro sitio:

```bash
FLATSAT_INSTALL_DIR=/opt/flatsat python flatsat_app.py install
```

Comandos disponibles tras instalar (en cualquier terminal):

| Comando | Qué hace |
|---|---|
| `flatsat web` | **Abre el dashboard en el navegador** |
| `flatsat doctor` | Diagnóstico: entorno, puertos serie y alias |
| `flatsat devices` | La placa conectada y sus puertos |
| `flatsat status` | Firmware, modo y estado del radio |
| `flatsat sensors` | Sensores en vivo |
| `flatsat sniff -n 3` | Capturar tramas CCSDS |
| `flatsat-web` | El dashboard directamente (atajo del menú Inicio) |
| `flatsat-gs` | La aplicación completa (dashboard + CLI + diagnóstico) |

Además crea accesos directos en el menú Inicio (Windows) o en
`~/.local/share/applications` (Linux).

> La instalación **no requiere permisos de administrador**: todo va a tu perfil.

---

---

### ⚠️ Si tu empresa bloquea los ejecutables sin firmar

Windows Defender Application Control (Device Guard / AppLocker) puede
rechazar el binario recién compilado:

```
'...\dist\flatsat-gs.exe' was blocked by your organization's Device Guard policy.
```

Es normal: el binario no está firmado.

**No hace falta hacer nada**: el instalador lo comprueba y cae solo a la vía
que funciona en tu equipo:

```
[!] El ejecutable flatsat-gs.exe está bloqueado por la política de seguridad del sistema.
[!]   Se instala la versión con Python: los mismos comandos, el mismo comportamiento.
```

La versión con Python usa el intérprete (que ya está autorizado) y unos
lanzadores `.cmd`. **Los comandos son idénticos** en cualquier equipo:

```bash
flatsat web            # dashboard
flatsat doctor         # diagnóstico
flatsat devices        # la placa
flatsat status
flatsat sniff -n 3
```

| Equipo | Qué instala el instalador |
|---|---|
| Sin política restrictiva | El binario autónomo (20 MB, sin Python) |
| Con Device Guard / AppLocker | Código + entorno virtual + lanzadores `.cmd` |

En los dos casos la instalación vive en `<proyecto>\flatsat-gs`, y
`flatsat-gs uninstall` la deja igual de limpia.

---

## 3. Verificar que todo funciona

```bash
flatsat-gs doctor
```

Salida esperada:

```
== Entorno ==
  Python:      3.11.9 (...)
  SO:          linux
  Directorio:  /home/usuario/.local/share/flatsat-ground-station/app
[+] Todas las dependencias de la aplicación están disponibles.

== Puertos serie detectados ==
 * /dev/ttyACM0                FlatSat Radio 0 [1209:BABC]
 * /dev/ttyACM1                FlatSat Radio 1 [1209:BABC]
 * /dev/ttyACM2                FlatSat Shell    [1209:BABC]

== Estado de la placa FlatSat ==
  /dev/ttyACM0: accesible (OK)
  /dev/ttyACM1: accesible (OK)
  /dev/ttyACM2: accesible (OK)
```

Prueba de humo del dashboard:

```bash
flatsat-web
# abre http://127.0.0.1:5000 → admin / password
```

Prueba de humo de la CLI:

```bash
flatsat devices
flatsat --help
```

---

## 4. Permisos de los puertos serie

La placa expone tres endpoints CDC-ACM: **Radio 0**, **Radio 1** y **Shell**.

### Linux

Opción A — grupo `dialout` (la habitual):

```bash
sudo usermod -aG dialout $USER
# cierra la sesión y vuelve a entrar
```

Opción B — regla udev (crea symlinks estables en `/dev/flatsat/`, no necesita
`dialout`):

```bash
sudo cp scripts/flatsat-udev.rules /etc/udev/rules.d/99-flatsat.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Windows

No hace falta nada: los puertos aparecen como `COMx` y el mapeador de puertos
ya gestiona `COM10+` automáticamente.

### macOS

Concede acceso en *Ajustes del Sistema → Privacidad y seguridad → Puertos de
serie*, o usa `/dev/cu.usbmodem*`.

---

## 5. Desinstalar

```bash
flatsat-gs uninstall
```

Elimina:

- el directorio de la instalación (`<proyecto>\flatsat-gs`): ejecutables,
  entorno virtual y base de datos
- los accesos directos del menú Inicio / `~/.local/share/applications`
- la entrada del PATH, **restaurando el PATH original**
- **los alias de la shell**: las funciones `flatsat` / `flatsat-web` /
  `flatsat-tui` del perfil de PowerShell y los completados de
  bash/zsh/fish que instaló `flatsat completion install`

Variantes:

```bash
flatsat-gs uninstall --keep-data   # conserva la telemetría en ~/.flatsat-ground-station/db/
```

También puedes desinstalar desde el repositorio:

```bash
python flatsat_app.py uninstall
```

> En Windows, si te desinstalas la app **con el comando instalado**, el
> directorio se borra unos segundos después: el `python.exe` del entorno
> virtual estaba en uso. El propio desinstalador te avisa con
> *"se borrará en unos segundos"*.

### 5.1 El alias de la CLI en tu terminal

La CLI se usa como un comando normal, sin scripts ni atajos raros:

```bash
flatsat devices        # cmd, PowerShell, Terminal (macOS), bash/zsh (Linux)
flatsat status
flatsat --help
```

**Instalar** pone el ejecutable en el PATH del usuario, así que funciona en
cualquier terminal. Si tenías alias antiguos definidos en el perfil de
PowerShell (los que inyectaba el antiguo `setup_windows.ps1`), **se eliminan al
instalar**: una función de PowerShell taparía al ejecutable y `flatsat` no
sería el comando nuevo.

**Desinstalar** los retira de nuevo, junto con el PATH y los completados.

> El script `setup_windows.ps1` se ha eliminado: hacía lo mismo que el
> instalador pero por otro camino, y esa duplicación era justo la fuente de
> los conflictos.

### 5.2 Desinstalar el paquete pip (si lo instalaste con `pip install`)

```bash
pip uninstall flatsat-ground-station
```

---

## 6. Usar el CLI mientras la webapp está conectada

La webapp **es la dueña de los puertos serie**. No se pueden abrir dos veces:
en Windows los dispositivos CDC-ACM se bloquean en exclusiva, y en Linux los
dos procesos se robarían bytes el uno al otro.

Hay dos formas de trabajar con las dos herramientas a la vez:

### Opción A — El CLI habla con la webapp (`-w`)

```bash
flatsat-web                 # la webapp conecta la placa

flatsat -w status           # estado leído a través de la webapp
flatsat -w sensors          # sensores
flatsat -w devices          # qué placa tiene la webapp conectada
flatsat -w sniff -n 10      # las tramas TM que la webapp está recibiendo
flatsat -w tc 0x20 --text PING
```

El flag `-w/--web` (por defecto `http://127.0.0.1:5000`) hace que el CLI use
la API REST de la webapp en lugar del puerto serie. Para apuntar a otra
instancia: `flatsat -w --web-url http://192.168.1.20:5000 sniff`.

> Da igual la terminal: cmd, PowerShell, la Terminal de macOS o bash.
> Lo único que hace falta es que la webapp esté corriendo en algún sitio.

> Muy útil para el taller: la webapp captura en directo y el CLI te muestra
> en la terminal lo que está entrando, sin pelearse por el puerto.

### Opción B — Desconectar en la webapp y usar el CLI

Pulsa **Disconnect** en el dashboard y luego usa el CLI con normalidad
(`flatsat status`, `flatsat sniff`...). Es la vía clásica para depurar la
placa con detalle.

---

## 7. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `Python was not found... Microsoft Store` | El alias de la Store tapa tu Python | Usa `py` o `run.cmd` (ver §2) |
| `python: command not found` (Linux/macOS) | Python no está instalado | Instálalo o usa el binario autónomo (Método A) |
| `No se pudo preparar el entorno` con `ensurepip` | Falta `python3-venv` | `sudo apt install python3-venv` |
| La placa no aparece en `flatsat devices` | Permisos del puerto serie | Ver §4, y luego `flatsat-gs doctor` |
| El puerto 5000 está ocupado (macOS) | AirPlay Receiver | `flatsat-web --port 5001` |
| `Address already in use` | Otro proceso en el puerto | `flatsat-web --port 5001` o `netstat -ano \| findstr :5000` |
| El navegador no se abre | Sin navegador por defecto | Abre <http://127.0.0.1:5000> a mano, o usa `--no-browser` |
| Error al compilar/instalar una dependencia | Sin ruedas para tu plataforma | Usa el binario autónomo (Método A) |
| `No se encuentra el .exe` | `dist/` está en `.gitignore` | Compílalo con `.
un.cmd build` (ver §2) |
| `flatsat` no se encuentra tras instalar | Terminal antigua | Abre una terminal nueva: el PATH se actualiza al iniciar sesión |
| El dashboard dice "HARDWARE" pero no llegan TM | La placa está en modo mock | Pulsa **Disconnect** y luego **Scan** + **Connect**: conectar la placa real nunca usa los puertos simulados |
| No llega nada por WebSocket | Sin internet y falta el cliente JS | El cliente Socket.IO va incluido en `webapp/static/js/socket-client.js`: no hace falta internet |
| No aparecen los logs `[RADIO0 RAW]` en un log redirigido | Buffering de stdout | Arranca con `python -u flatsat_app.py web` para ver los logs en tiempo real |

---

## 8. Para mantenedores — compilar el binario

Hay **un solo spec** (`flatsat_app.spec`) y **un solo binario**:

```bash
# Linux / macOS
./compile_app.sh                 # → dist/flatsat-gs
./compile_app.sh --bundle        # → + .app/.dmg (macOS) o AppImage (Linux)

# Windows
.\run.cmd build                 # → dist\flatsat-gs.exe
```

> **En PowerShell los ficheros del directorio actual necesitan el prefijo
> `.\`** (`.\\build_app_windows.bat`), si no dice *"no se reconoce como un
> cmdlet"*. `run.cmd build` funciona igual porque el propio script resuelve
> su ruta.

Equivalente con make: `make app-build`.

> **Guía completa por plataforma** (requisitos, compilación, instalación,
> permisos y problemas): [Compilar e instalar](building.md)

Ese mismo binario sirve para el dashboard y para el CLI: son el mismo
programa con distinto nombre. Y **se instala a sí mismo**:

```bash
dist\flatsat-gs.exe install     # Windows
./dist/flatsat-gs install       # Linux / macOS
```

No hace falta ningún otro instalador.

---

## 9. Comandos de referencia

```bash
# Dashboard
flatsat-web --port 5001        # puerto alternativo
flatsat-web --level 3          # nivel CTF: 1 fácil, 2 medio, 3 difícil
flatsat-web --no-mock          # sin telemetría simulada
flatsat-web --no-browser       # no abrir el navegador

# CLI
flatsat devices                # placas conectadas y sus endpoints
flatsat status                 # estado y versión de firmware
flatsat sensors                # telemetría en vivo (BME280, LIS2DH)
flatsat sniff -n 10 -o cap.json   # capturar 10 tramas CCSDS
flatsat tc 0x20 --text "PING"  # enviar una telecomando
flatsat mode gs                # cambiar la placa a modo estación
flatsat attack --help          # escenarios de ataque CTF

# CLI contra una webapp que ya tiene la placa conectada
flatsat -w status              # estado vía webapp
flatsat -w sniff -n 10         # ver en la terminal lo que recibe la webapp
flatsat -w tc 0x20 --text PING # enviar una telecomando vía webapp

# Diagnóstico
flatsat-gs doctor              # entorno + puertos serie
flatsat-gs version
```

---

## 10. Recursos

- [Compilar e instalar (Windows, Linux, macOS)](building.md)
- [Probar el CLI (checklist)](cli-testing.md)
- [Walkthrough del CTF](ctf_walkthrough_guide.md)
- [Plan de taller y currículo](curriculum-plan.md)
- [Guía de pruebas con dos placas](cli_two_board_testing.md)
- [Repositorio](https://github.com/ElectronicCats/flatsat-ground-station)
