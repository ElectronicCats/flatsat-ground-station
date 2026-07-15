"""Custom help menu rendering."""


def print_help_menu():
    help_text = """\033[1;33m=== COMANDOS DISPONIBLES ===\033[0m
  \033[1mflatsat devices\033[0m     - Muestra las placas FlatSat conectadas y sus puertos.
  \033[1mflatsat status\033[0m      - Verifica si el satélite responde y qué radios están activas.
  \033[1mflatsat sensors\033[0m     - Muestra las lecturas de los sensores (temperatura, aceleración, etc.).
  \033[1mflatsat mode [gs|sat]\033[0m- Cambia entre modo SAT (satélite automático) y GS (estación de tierra).
  \033[1mflatsat flight [state]\033[0m- Cambia o lee el estado de vuelo (safe, nominal, idle, debug).
  \033[1mflatsat difficulty [N]\033[0m- Configura o lee el nivel del taller (Nivel 1, 2 o 3).
  \033[1mflatsat color [R G B]\033[0m - Cambia el color del LED Neopixel en la placa (valores 0-255).
  \033[1mflatsat identify\033[0m    - Hace parpadear los LEDs físicos de la placa para ubicarla.
  \033[1mflatsat reboot\033[0m      - Reinicia la placa y la manda a modo de carga de firmware (BOOTSEL).
  \033[1mflatsat cmd "[comando]"\033[0m- Envía un comando de texto crudo directamente a la terminal de la placa.
  \033[1mflatsat config\033[0m      - Configura y aplica parámetros LoRa de las radios.
      \033[3mParámetros de config:\033[0m
      --radio [0|1]     (Selecciona la radio a configurar)
      --freq [Hz]       (Frecuencia, ej: 915000000)
      --sf [7-12]       (Spreading Factor)
      --bw [125|250|500](Bandwidth en kHz)
      --cr [5-8]        (Coding Rate)
      --power [dBm]     (Potencia de transmisión)
      --syncword [val]  (Palabra de sincronía, ej: 0x2D)
      --mode [stream|command] (Modo de la radio)
      --apply           (Aplica los cambios staged al hardware inmediatamente)
"""
    print(help_text)
