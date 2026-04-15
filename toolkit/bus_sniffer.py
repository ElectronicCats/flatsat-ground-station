#!/usr/bin/env python3
"""HW-03: Bus sniffer — decode SPI/I2C/UART captures from logic analyzer.

Processes CSV exports from logic analyzers (Saleae Logic, sigrok/PulseView)
to extract and decode data from the FlatSat's internal buses:
- SPI: LoRa radio register access (SX1276/SX1262)
- I2C: BME280 sensor reads, LIS2DH accelerometer
- UART: Shell commands, debug output

Participants probe the FlatSat PCB test points to capture bus traffic.
"""

import csv
import sys

# I2C device addresses on the FlatSat
I2C_DEVICES = {
    0x76: "BME280 (temperature/pressure/humidity)",
    0x77: "BME280 (alt address)",
    0x18: "LIS2DH (accelerometer)",
    0x19: "LIS2DH (alt address)",
    0x50: "EEPROM",
}

# SPI LoRa register names (SX1276)
SX1276_REGS = {
    0x00: "RegFifo",
    0x01: "RegOpMode",
    0x06: "RegFrfMsb",
    0x07: "RegFrfMid",
    0x08: "RegFrfLsb",
    0x09: "RegPaConfig",
    0x0B: "RegOcp",
    0x0C: "RegLna",
    0x0D: "RegFifoAddrPtr",
    0x0E: "RegFifoTxBaseAddr",
    0x0F: "RegFifoRxBaseAddr",
    0x10: "RegFifoRxCurrentAddr",
    0x12: "RegIrqFlags",
    0x13: "RegRxNbBytes",
    0x1D: "RegModemConfig1",
    0x1E: "RegModemConfig2",
    0x20: "RegPreambleMsb",
    0x21: "RegPreambleLsb",
    0x22: "RegPayloadLength",
    0x26: "RegModemConfig3",
    0x39: "RegSyncWord",
    0x40: "RegDioMapping1",
}

# BME280 registers
BME280_REGS = {
    0xD0: "chip_id",
    0xE0: "reset",
    0xF2: "ctrl_hum",
    0xF3: "status",
    0xF4: "ctrl_meas",
    0xF5: "config",
    0xF7: "press_msb",
    0xF8: "press_lsb",
    0xF9: "press_xlsb",
    0xFA: "temp_msb",
    0xFB: "temp_lsb",
    0xFC: "temp_xlsb",
    0xFD: "hum_msb",
    0xFE: "hum_lsb",
}


def decode_spi_csv(filepath: str):
    """Decode SPI captures from Saleae Logic CSV export.

    Expected columns: Time [s], Packet ID, MOSI, MISO
    """
    print(f"[*] Parsing SPI capture: {filepath}")
    transactions = []

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = float(row.get("Time [s]", row.get("time", 0)))
            mosi = row.get("MOSI", row.get("mosi", ""))
            miso = row.get("MISO", row.get("miso", ""))

            if not mosi:
                continue

            try:
                mosi_val = int(mosi, 0)
            except ValueError:
                continue

            # SPI LoRa: first byte is register | 0x80 for write
            is_write = bool(mosi_val & 0x80)
            reg = mosi_val & 0x7F
            reg_name = SX1276_REGS.get(reg, f"0x{reg:02X}")
            direction = "WRITE" if is_write else "READ"

            try:
                miso_val = int(miso, 0) if miso else None
            except ValueError:
                miso_val = None

            transactions.append(
                {
                    "time": ts,
                    "direction": direction,
                    "register": reg_name,
                    "reg_addr": reg,
                    "mosi": mosi_val,
                    "miso": miso_val,
                }
            )

    print(f"[*] {len(transactions)} SPI transactions decoded")
    print()

    # Analyze interesting transactions
    freq_regs = {}
    for t in transactions:
        addr = t["reg_addr"]
        print(
            f"  [{t['time']:.6f}] {t['direction']:5s} {t['register']:20s} "
            f"MOSI=0x{t['mosi']:02X}" + (f" MISO=0x{t['miso']:02X}" if t["miso"] is not None else "")
        )

        # Track frequency register writes
        if t["direction"] == "WRITE" and addr in (0x06, 0x07, 0x08):
            freq_regs[addr] = t["mosi"] if t["miso"] is None else t["miso"]

    # Calculate frequency if we have all three registers
    if len(freq_regs) == 3:
        frf = (freq_regs[0x06] << 16) | (freq_regs[0x07] << 8) | freq_regs[0x08]
        freq_hz = frf * 32e6 / (2**19)
        print(f"\n[+] Configured frequency: {freq_hz / 1e6:.3f} MHz")


def decode_i2c_csv(filepath: str):
    """Decode I2C captures from Saleae Logic CSV export.

    Expected columns: Time [s], Address, Data, Read/Write
    """
    print(f"[*] Parsing I2C capture: {filepath}")

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = float(row.get("Time [s]", row.get("time", 0)))
            addr = int(row.get("Address", row.get("address", "0")), 0)
            data = row.get("Data", row.get("data", ""))
            direction = row.get("Read/Write", row.get("direction", ""))

            device = I2C_DEVICES.get(addr, f"Unknown (0x{addr:02X})")
            is_read = "read" in direction.lower()

            # Parse data bytes
            try:
                data_bytes = bytes.fromhex(data.replace("0x", "").replace(" ", ""))
            except ValueError:
                data_bytes = b""

            reg_info = ""
            if data_bytes and addr in (0x76, 0x77):
                reg = data_bytes[0]
                reg_info = f" reg={BME280_REGS.get(reg, f'0x{reg:02X}')}"

            print(f"  [{ts:.6f}] {'READ' if is_read else 'WRITE':5s} {device:40s} data={data_bytes.hex()}{reg_info}")


def decode_uart_csv(filepath: str, baud: int = 115200):
    """Decode UART captures — extract shell commands and responses."""
    print(f"[*] Parsing UART capture: {filepath}")

    text_buf = ""
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data = row.get("Data", row.get("data", row.get("Value", "")))
            try:
                byte_val = int(data, 0)
                char = chr(byte_val) if 32 <= byte_val < 127 or byte_val in (10, 13) else "."
                text_buf += char
            except (ValueError, TypeError):
                if data:
                    text_buf += data

    # Split into lines and display
    lines = text_buf.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    print(f"[*] {len(lines)} lines decoded:")
    print()
    for line in lines:
        if line.strip():
            # Highlight interesting patterns
            prefix = "  "
            if any(kw in line.lower() for kw in ["pwnsat{", "flag", "password", "key"]):
                prefix = "  [FLAG] "
            elif any(kw in line.lower() for kw in ["error", "fault", "fail"]):
                prefix = "  [ERR]  "
            print(f"{prefix}{line}")


def generate_sample(protocol: str, output: str):
    """Generate a sample CSV file for testing."""
    if protocol == "spi":
        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time [s]", "Packet ID", "MOSI", "MISO"])
            writer.writerow(["0.000100", "0", "0x86", "0x00"])  # Write RegFrfMsb
            writer.writerow(["0.000200", "1", "0x87", "0x00"])  # Write RegFrfMid
            writer.writerow(["0.000300", "2", "0x88", "0x00"])  # Write RegFrfLsb
            writer.writerow(["0.000400", "3", "0x01", "0x80"])  # Read RegOpMode -> LoRa
        print(f"[*] Sample SPI CSV written to {output}")

    elif protocol == "i2c":
        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time [s]", "Address", "Data", "Read/Write"])
            writer.writerow(["0.001", "0x76", "0xD0", "Write"])
            writer.writerow(["0.002", "0x76", "0x60", "Read"])
        print(f"[*] Sample I2C CSV written to {output}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  bus_sniffer.py spi <capture.csv>      Decode SPI (LoRa radio registers)")
        print("  bus_sniffer.py i2c <capture.csv>       Decode I2C (sensors)")
        print("  bus_sniffer.py uart <capture.csv>      Decode UART (shell traffic)")
        print("  bus_sniffer.py sample <spi|i2c> <out>  Generate sample CSV for testing")
        print()
        print("Process logic analyzer CSV exports (Saleae Logic, sigrok/PulseView)")
        print("to extract data from FlatSat internal buses.")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "spi":
        decode_spi_csv(sys.argv[2])
    elif cmd == "i2c":
        decode_i2c_csv(sys.argv[2])
    elif cmd == "uart":
        decode_uart_csv(sys.argv[2])
    elif cmd == "sample":
        generate_sample(sys.argv[2], sys.argv[3])
