#!/usr/bin/env python3
"""
Prueba Individual - Ataque 1: Enumeración de la API
Verifica la divulgación de endpoints del servidor en tierra sin autenticación.
"""
import requests

BASE_URL = "http://localhost:5000"

def test_attack_1():
    print("[+] Ejecutando Prueba Individual: Ataque 1 - Enumeración de API...")
    url = f"{BASE_URL}/api/endpoints"
    try:
        response = requests.get(url, timeout=5)
        print(f"[*] GET {url} - Status Code: {response.status_code}")
        if response.status_code == 200:
            endpoints = response.json()
            print("[✓] Vulnerabilidad confirmada! Endpoints expuestos:")
            for ep in endpoints:
                print(f"    - {ep}")
        else:
            print(f"[!] Respuesta inesperada: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_1()
