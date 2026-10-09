#!/usr/bin/env python3
"""
Ejecutor de Pruebas Individuales para los 8 Ataques de FlatSat
Uso: python3 run_individual_attack.py --attack <numero 1-8>
"""
import argparse
import os
import subprocess
import sys

ATTACKS = {
    1: ("Enumeración de la API", "attacks/attack_1_api_enum.py"),
    2: ("Inyección SQL (SQLi)", "attacks/attack_2_sqli.py"),
    3: ("Falsificación de Sesión (Session Tampering)", "attacks/attack_3_session_forging.py"),
    4: ("Inclusión de Archivos Locales (LFI)", "attacks/attack_4_lfi.py"),
    5: ("Ejecución Remota de Código (RCE)", "attacks/attack_5_rce.py"),
    6: ("Insecure Direct Object Reference (IDOR)", "attacks/attack_6_idor.py"),
    7: ("Inyección de Comando en Claro (Spoofing TEST)", "attacks/attack_7_rf_plaintext.py"),
    8: ("Desbordamiento de Pila en Firmware (DIAG_MEM Overflow)", "attacks/attack_8_fw_overflow.py"),
}

def main():
    parser = argparse.ArgumentParser(description="Ejecutar uno de los 8 ataques de FlatSat de forma individual.")
    parser.add_argument("-a", "--attack", type=int, choices=range(1, 9), help="Número de ataque a probar (1 al 8)")
    args = parser.parse_args()

    attack_num = args.attack

    if attack_num is None:
        print("=== Menú de Pruebas Individuales de Ataques FlatSat ===")
        for num, (name, _script) in ATTACKS.items():
            print(f"  [{num}] Ataque {num}: {name}")
        print("======================================================")
        try:
            val = input("Selecciona el número de ataque que deseas probar (1-8): ").strip()
            attack_num = int(val)
        except (ValueError, KeyboardInterrupt):
            print("\n[!] Entrada no válida o cancelada.")
            sys.exit(1)

    if attack_num not in ATTACKS:
        print(f"[X] Número de ataque no válido: {attack_num}")
        sys.exit(1)

    name, script = ATTACKS[attack_num]
    script_path = os.path.join(os.path.dirname(__file__), script)

    print(f"\n>>> Iniciando prueba del Ataque {attack_num}: {name} <<<\n")
    # noqa comment: fixed argv list, no shell; script_path comes from ATTACKS above.
    subprocess.run([sys.executable, script_path])  # noqa: S603

if __name__ == "__main__":
    main()
