"""Serial port diagnostics for the FlatSat ground station.

Docker is a poor fit for the FlatSat boards: every CDC-ACM endpoint has to
be bind-mounted individually, the container user rarely matches the host's
``dialout`` group, and the tty device nodes change on every replug.  Running
the ground station natively is the supported path for hardware work, and this
module explains exactly why a board is (not) detected.

Used by ``flatsat_app.py doctor`` and by ``scripts/serial_doctor.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from modules.core.constants import USB_PID, USB_VID
except Exception:  # noqa: BLE001 - pyserial may be missing, and modules.core imports it
    # Fallback values: importing modules.core pulls in modules.core.device,
    # which needs pyserial. The USB ids are stable, so hardcode them here to
    # keep the diagnostic usable even in a half-installed environment.
    USB_VID = 0x1209
    USB_PID = 0xBABC

# Import name -> pip package name, for the "missing dependency" report.
_SERIAL_MODULES = {"serial": "pyserial"}


def _iter_ports() -> list[dict]:
    """Return every serial port visible to the OS, as plain dicts."""
    try:
        import serial.tools.list_ports as list_ports
    except ImportError:
        return []

    ports = []
    for p in list_ports.comports():
        ports.append(
            {
                "device": p.device,
                "description": p.description or "",
                "hwid": p.hwid or "",
                "vid": getattr(p, "vid", None),
                "pid": getattr(p, "pid", None),
                "serial_number": getattr(p, "serial_number", None),
                "manufacturer": getattr(p, "manufacturer", None) or "",
                "product": getattr(p, "product", None) or "",
                "is_flatsat": _looks_like_flatsat(p),
            }
        )
    return ports


def _looks_like_flatsat(port) -> bool:
    """True when a pyserial ListPortInfo belongs to a FlatSat / CatSniffer board."""
    if getattr(port, "vid", None) == USB_VID and getattr(port, "pid", None) == USB_PID:
        return True
    hwid = (getattr(port, "hwid", "") or "").upper()
    if "1209" in hwid and "BABC" in hwid:
        return True
    text = f"{getattr(port, 'description', '') or ''} {getattr(port, 'product', '') or ''}".upper()
    return any(k in text for k in ("FLATSAT", "CATSNIFFER", "ELECTRONIC CATS", "CAT-SHELL", "CAT-RADIO"))


def _can_open(port_path: str) -> tuple[bool, str]:
    """Try to open the port read-only to verify the OS permissions."""
    try:
        import serial
    except ImportError:
        return False, "pyserial no está instalado"

    try:
        with serial.Serial(port_path, timeout=0.2) as ser:
            ser.read(1)
        return True, "OK"
    except Exception as exc:  # noqa: BLE001 - any failure is a permission/driver problem
        return False, f"{type(exc).__name__}: {exc}"


def _linux_permission_hints() -> list[str]:
    """Return actionable hints for Linux dialout / udev problems."""
    hints: list[str] = []
    if sys.platform != "linux":
        return hints

    try:
        import grp

        groups = {g.gr_name for g in grp.getgrall()}
        if "dialout" in groups:
            hints.append(
                "El grupo 'dialout' existe. Si acabas de añadirte con "
                "'sudo usermod -aG dialout $USER', cierra la sesión y vuelve a entrar."
            )
        else:
            hints.append(
                "El grupo 'dialout' no existe: instálalo con 'sudo apt install dialout' "
                "o usa la regla udev de scripts/flatsat-udev.rules."
            )
    except Exception:  # noqa: BLE001 - grp is unavailable on some embedded pythons
        pass

    dev_glob = list(Path("/dev").glob("ttyACM*")) + list(Path("/dev").glob("ttyUSB*"))
    if not dev_glob:
        hints.append(
            "No hay /dev/ttyACM* ni /dev/ttyUSB*. El kernel no ha enumerated la placa: "
            "prueba otro cable USB (de datos, no solo de carga) o ejecuta 'dmesg | tail'."
        )
        return hints

    for dev in dev_glob:
        try:
            st = dev.stat()
        except OSError:
            continue
        hints.append(f"{dev} -> grupo {st.st_gid} (usa 'ls -l {dev}' para ver el nombre del grupo).")
    return hints


def diagnose(verbose: bool = True) -> dict:
    """Collect a full serial-port report.

    Returns a dict with the raw ports plus a human readable ``report`` string.
    """
    lines: list[str] = []
    ports = _iter_ports()

    lines.append("== Puertos serie detectados ==")
    if not ports:
        lines.append("  (ninguno)")
    for p in ports:
        marker = "*" if p["is_flatsat"] else " "
        vidpid = ""
        if p["vid"] is not None and p["pid"] is not None:
            vidpid = f" [{p['vid']:04X}:{p['pid']:04X}]"
        lines.append(f" {marker} {p['device']:<24} {p['description']}{vidpid}")

    flatsat_ports = [p for p in ports if p["is_flatsat"]]
    lines.append("")
    lines.append("== Estado de la placa FlatSat ==")
    if not flatsat_ports:
        lines.append("  No se ha detectado ninguna placa FlatSat/CatSniffer.")
    else:
        for p in flatsat_ports:
            ok, detail = _can_open(p["device"])
            state = "accesible" if ok else "BLOQUEADO"
            lines.append(f"  {p['device']}: {state} ({detail})")
        if len(flatsat_ports) < 3:
            lines.append(
                f"  Solo {len(flatsat_ports)} de 3 endpoints visibles. Una placa FlatSat expone "
                "CDC0 (Radio 0), CDC1 (Radio 1) y CDC2 (Shell)."
            )

    hints = _linux_permission_hints()
    if hints:
        lines.append("")
        lines.append("== Sugerencias ==")
        for h in hints:
            lines.append(f"  - {h}")

    if verbose:
        try:
            import serial  # noqa: F401

            lines.append("")
            lines.append("pyserial: OK")
        except ImportError:
            lines.append("")
            lines.append(f"pyserial: FALTA -> ejecuta 'pip install pyserial' (paquete: {_SERIAL_MODULES['serial']})")

    return {
        "ports": ports,
        "flatsat_ports": flatsat_ports,
        "hints": hints,
        "report": "\n".join(lines),
    }


def main() -> int:
    """Print the serial report to stdout."""
    report = diagnose()
    print(report)
    return 0 if report["flatsat_ports"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
