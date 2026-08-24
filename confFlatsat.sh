#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Configura el enlace completo (satélite + ground station), permitiendo elegir
# el nivel de dificultad SDLS. La dificultad se aplica a AMBOS dispositivos.
#
# Uso:
#   ./confFlatsat.sh          -> dificultad 1 (por defecto)
#   ./confFlatsat.sh -d 2     -> dificultad 2
#   ./confFlatsat.sh -d 3     -> dificultad 3
#
#   1 -> sin cifrado | 2 -> XOR | 3 -> AES-128-CTR
# ---------------------------------------------------------------------------

# --- Parseo de argumentos: -d/--difficulty, -s/--sat, -g/--gs ---
DIFFICULTY=1
SAT="${SAT:-5033423532300010}"   # Satélite (por defecto)
GS="${GS:-503342353230000E}"     # Ground station (por defecto)

usage() {
    echo "Uso: $0 [-d <1|2|3>] [-s <serial_sat>] [-g <serial_gs>]" >&2
    echo "  -d, --difficulty   Nivel de dificultad SDLS (1-3), aplicado a SAT y GS. Por defecto: 1." >&2
    echo "  -s, --sat          Número de serie del Satélite. Por defecto: $SAT" >&2
    echo "  -g, --gs           Número de serie de la Ground Station. Por defecto: $GS" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--difficulty)
            [[ $# -ge 2 ]] || { echo "Error: '$1' requiere un valor." >&2; usage; }
            DIFFICULTY="$2"
            shift 2
            ;;
        -s|--sat)
            [[ $# -ge 2 ]] || { echo "Error: '$1' requiere un valor." >&2; usage; }
            SAT="$2"
            shift 2
            ;;
        -g|--gs)
            [[ $# -ge 2 ]] || { echo "Error: '$1' requiere un valor." >&2; usage; }
            GS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Error: argumento desconocido '$1'." >&2
            usage
            ;;
    esac
done

# Validar que la dificultad sea 1, 2 o 3.
case "$DIFFICULTY" in
    1|2|3) ;;
    *) echo "Error: la dificultad debe ser 1, 2 o 3 (recibido: '$DIFFICULTY')." >&2; usage ;;
esac

# Activar el entorno virtual si está presente.
if [[ -f "$HOME/FlatSatEnv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/FlatSatEnv/bin/activate"
elif [[ -f "$(dirname "$0")/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$(dirname "$0")/.venv/bin/activate"
fi

# Los alias (p.ej. `alias flatsat=...`) NO se expanden dentro de un script,
# así que definimos aquí cómo se invoca la CLI. Ajusta la ruta si es necesario.
FLATSAT="${FLATSAT:-python3 $(dirname "$0")/flatsat_cli.py}"

# ---------------------------------------------------------------------------
# 1) Parámetros RF del enlace. Las frecuencias van CRUZADAS entre placas,
#    porque la radio que transmite en una debe emparejarse con la que escucha
#    en la otra:
#
#      915 MHz -> UPLINK   (telecomandos):  GS radio 1  ->  SAT radio 0
#      916 MHz -> DOWNLINK (telemetría):    SAT radio 1 ->  GS  radio 0
#
#    sf/bw/cr/power/syncword sí son idénticos en las cuatro radios. Igual que el
#    webapp (applyLora fija freq/sf/bw/power), aquí NO fijamos el lora_mode:
#    de eso se encarga el paso 2 (`flatsat mode`).
# ---------------------------------------------------------------------------

# --- Ground station: parámetros RF ---
# R0 @ 916 MHz: RX de la telemetría que baja del satélite (downlink).
$FLATSAT config --radio 0 --freq 916000000 --mode command  --sf 7 --bw 125 --cr 5 --power 20 --syncword private --apply -d "$GS"
# R1 @ 915 MHz: TX de los telecomandos hacia el satélite (uplink).
$FLATSAT config --radio 1 --freq 915000000 --mode stream   --sf 7 --bw 125 --cr 5 --power 20 --syncword private --apply -d "$GS"

# --- Satélite: parámetros RF ---
# R0 @ 915 MHz: RX de los telecomandos que envía la GS (uplink).
$FLATSAT config --radio 0 --freq 915000000 --mode command  --sf 7 --bw 125 --cr 5 --power 20 --syncword private --apply -d "$SAT"
# R1 @ 916 MHz: TX de la telemetría hacia la GS (downlink).
$FLATSAT config --radio 1 --freq 916000000 --mode stream   --sf 7 --bw 125 --cr 5 --power 20 --syncword private --apply -d "$SAT"

# ---------------------------------------------------------------------------
# 2) Rol de cada placa con el comando `mode` del CLI (idéntico al webapp,
#    webapp/app.py api_satellite_mode):
#      mission        -> mode sat + lora_mode ALL stream               (rol satélite)
#      ground_station -> mode gs  + lora_apply ALL + lora_mode ALL command (rol GS)
#
#    IMPORTANTE: el satélite mantiene AMBAS radios en stream. El firmware acopla
#    el rol al lora_mode: una radio en `command` hace que la placa se comporte
#    como ground station. Por eso NO se pone R0 en command en el satélite (lo
#    sacaría del rol satélite). El `--mode command` de R0 en el paso 1 queda
#    sobreescrito por `mode mission` — es intencional.
#
#    NOTA: `mode ground_station` deja AMBAS radios de la GS en command, igual
#    que el webapp. El puente de radio (RadioBridge) alterna por transmisión:
#    TX en Radio 1 @ 915 MHz (command) y vuelve a Radio 0 @ 916 MHz para
#    escuchar telemetría, así que NO reactivamos stream en R1 aquí para no
#    divergir del webapp. Las frecuencias fijadas en el paso 1 se conservan:
#    `mode` sólo cambia el rol y el lora_mode, no la frecuencia.
#    NOTA: los comandos del CLI ya NO se pisan entre sí. Conectarse dejó de
#    forzar el modo (core/device.py connect(forced_role=None) por defecto), así
#    que cada `$FLATSAT` conserva el modo en que quedó la placa.
# ---------------------------------------------------------------------------
$FLATSAT mode ground_station -d "$GS"

# El satélite entra en modo misión ANTES de fijar difficulty/flight: así ya
# está en rol satélite y el comando `flight` lo detecta y lo fija por USB
# directo (no por RF).
$FLATSAT mode mission -d "$SAT"

# ---------------------------------------------------------------------------
# 2b) Nivel de dificultad/seguridad SDLS (1-3). Se fija en AMBOS dispositivos:
#     el satélite lo usa para cifrar la telemetría y validar los telecomandos,
#     y la GS para craftear los telecomandos y descifrar la telemetría. Aunque
#     la GS también lo autodetecta de los heartbeats, lo fijamos explícitamente
#     para que el uplink case desde el primer telecomando (evita error_count).
#       1 -> sin cifrado | 2 -> XOR | 3 -> AES-128-CTR
# ---------------------------------------------------------------------------
$FLATSAT difficulty "$DIFFICULTY" -d "$SAT"
$FLATSAT difficulty "$DIFFICULTY" -d "$GS"

# ---------------------------------------------------------------------------
# 2c) Estado de vuelo del satélite: el firmware SUPRIME las balizas/telemetría
#     en IDLE y SAFE. Para que EMITA hay que dejarlo en NOMINAL (igual que la
#     webapp al pulsar "Nominal"). Como la placa ya está en modo satélite, el
#     CLI manda `flight nominal` directo por USB.
# ---------------------------------------------------------------------------
$FLATSAT flight nominal -d "$SAT"

clear

# ---------------------------------------------------------------------------
# 3) Colores ANSI y panel de dificultad. Se usan bytes de escape reales
#    ($'\033[...]') para que funcionen bajo bash (el `echo "\033..."` plano NO
#    los interpreta en bash). El nivel SDLS se traduce a nombre, medidor y color:
#      1 SIN CIFRADO -> rojo | 2 XOR -> amarillo | 3 AES-128-CTR -> verde
# ---------------------------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; RST=$'\033[0m'
CYAN=$'\033[96m'; GREEN=$'\033[92m'; YELLOW=$'\033[93m'; RED=$'\033[91m'; MAGENTA=$'\033[95m'

case "$DIFFICULTY" in
    1) DIFF_NAME="SIN CIFRADO"; DIFF_COLOR="$RED";
       DIFF_BAR="█████░░░░░░░░░░░"; DIFF_DOTS="(●)( )( )" ;;
    2) DIFF_NAME="XOR";         DIFF_COLOR="$YELLOW";
       DIFF_BAR="██████████░░░░░"; DIFF_DOTS="(●)(●)( )" ;;
    3) DIFF_NAME="AES-128-CTR"; DIFF_COLOR="$GREEN";
       DIFF_BAR="███████████████"; DIFF_DOTS="(●)(●)(●)" ;;
esac

# --- Identidad y dificultad de cada placa (una línea por dispositivo) ---
echo "${BOLD}${MAGENTA}  SATÉLITE${RST}        ${DIM}serial${RST} ${SAT}   ${DIFF_COLOR}${BOLD}SDLS ${DIFFICULTY} · ${DIFF_NAME}${RST}"
echo "${BOLD}${MAGENTA}  GROUND STATION${RST}  ${DIM}serial${RST} ${GS}   ${DIFF_COLOR}${BOLD}SDLS ${DIFFICULTY} · ${DIFF_NAME}${RST}"

# ---------------------------------------------------------------------------
# 4) Resumen del enlace configurado.
# ---------------------------------------------------------------------------
cat <<EOF

${BOLD}${MAGENTA}   ╔═══════════════════════════════════════════════════════════════╗
   ║               CONFIGURACIÓN FINAL DEL ENLACE                  ║
   ╚═══════════════════════════════════════════════════════════════╝${RST}

        ${BOLD}GROUND STATION${RST}                                ${BOLD}SATÉLITE${RST}
   ┌──────────────────────┐                      ┌──────────────────────┐
   │  R0  916 MHz  (RX)   │ ${CYAN}<═══ DOWNLINK ══════${RST} │  R1  916 MHz  (TX)   │
   │      command         │ ${CYAN}     TELEMETRÍA     ${RST} │      stream          │
   │                      │                      │                      │
   │  R1  915 MHz  (TX)   │ ${GREEN}═══ UPLINK ════════>${RST} │  R0  915 MHz  (RX)   │
   │      stream          │ ${GREEN}    TELECOMANDOS    ${RST} │      command         │
   └──────────────────────┘                      └──────────────────────┘
        mode: ground_station                          mode: mission
        ${DIFF_COLOR}SDLS ${DIFFICULTY} · ${DIFF_NAME}${RST}                            ${DIFF_COLOR}SDLS ${DIFFICULTY} · ${DIFF_NAME}${RST}

   ${BOLD}Parámetros comunes a las 4 radios:${RST}
     SF 7 | BW 125 kHz | CR 4/5 | TX power 20 dBm | syncword private

   ${BOLD}Dificultad SDLS del enlace${RST}
   ┌────────────────────────────────────────────────────────────────┐
   │
   │   Nivel ${DIFF_COLOR}${BOLD}${DIFFICULTY}${RST}/3   ${DIFF_COLOR}${DIFF_DOTS}${RST}   ${DIFF_COLOR}${BOLD}${DIFF_NAME}${RST}
   │   ${DIFF_COLOR}[${DIFF_BAR}]${RST}
   │
   └────────────────────────────────────────────────────────────────┘
     ${DIM}1 = sin cifrado    2 = XOR    3 = AES-128-CTR${RST}

   * El satélite TRANSMITE la TELEMETRÍA en 916 MHz (su R1 -> R0 de la GS).
   * El satélite RECIBE los TELECOMANDOS en 915 MHz (R1 de la GS -> su R0).

EOF

