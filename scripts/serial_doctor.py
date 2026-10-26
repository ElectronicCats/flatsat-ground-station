#!/usr/bin/env python3
"""Diagnóstico de puertos serie para la WebApp de FlatSat Ground Station.

Uso:
    python scripts/serial_doctor.py

Devuelve 0 si se detecta una placa FlatCat/CatSniffer accesible, 1 si no.
Es el equivalente nativo (sin Docker) al chequeo de dispositivos USB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.utils.serial_doctor import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
