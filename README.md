[README.md](https://github.com/user-attachments/files/28727797/README.md)
# PwnSat Ground Station

A Flask-based ground station for communicating with PwnSat2 FlatSat hardware via LoRa radio. Designed for educational CTF (Capture The Flag) exercises where participants interact with real satellite hardware through a web dashboard.

## Requirements

- Python 3.11+
- pip

Optional for hardware mode:
- FlatSat device (USB VID:PID `0x1209:0xBABC`)
- Linux recommended for USB device discovery (uses `pyudev`)

## Quick Start

### Linux / macOS
```bash
git clone <repo-url>
cd flatsat-ground-station
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLATSAT_LEVEL=1  # 1: Easy, 2: Medium, 3: Hard
# Optional (for single-radio hardware like CatSniffer): export FLATSAT_SINGLE_RADIO=1
python -m webapp.app
```

### Windows (PowerShell)
```powershell
git clone <repo-url>
cd flatsat-ground-station
# If PowerShell script execution is disabled, run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FLATSAT_LEVEL="1"  # 1: Easy, 2: Medium, 3: Hard
# Optional (for single-radio hardware like CatSniffer): $env:FLATSAT_SINGLE_RADIO="1"
python -m webapp.app
```

### Windows (Command Prompt - CMD)
```cmd
git clone <repo-url>
cd flatsat-ground-station
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
set FLATSAT_LEVEL=1  # 1: Easy, 2: Medium, 3: Hard
# Optional (for single-radio hardware like CatSniffer): set FLATSAT_SINGLE_RADIO=1
python -m webapp.app
```


### CTF Difficulty Levels

This ground station supports three difficulty levels that toggle security vulnerabilities and protocol complexity:

- **Level 1 (Easy):** Web vulnerabilities (SQLi, Auth Bypass) are fully exploitable. Radio communication is in plaintext.
- **Level 2 (Medium):** Web vulnerabilities are harder (LFI, RCE). Radio requires CCSDS Space Packets.
- **Level 3 (Hard):** Web security is hardened (Signed tokens, input validation). Focus shifts to firmware exploitation (Buffer Overflows) and SDLS/AES crypto.

Change the level using the `FLATSAT_LEVEL` environment variable before starting the app.

If using a single-radio board like the **CatSniffer** as the Ground Station, you must also set the `FLATSAT_SINGLE_RADIO` environment variable to `1` (e.g., `export FLATSAT_SINGLE_RADIO=1` or `$env:FLATSAT_SINGLE_RADIO="1"`) to prevent the webapp/microcontroller from freezing during telecommand transmission.

Open `http://localhost:5000` in your browser.

The database is created automatically on first run. No manual setup needed.

> **Credentials:** Ask your instructor for login details.

### Simulated Mode

Click **Simulate** on the dashboard to generate mock telemetry without hardware. Useful for development and CTF setup.

### Hardware Mode (Two-Board Setup)

This system uses a **two-board setup** to simulate real-world space communication:
*   **CatSniffer (`E661A897539C4732`)** acts as the **Ground Station** (connected to the PC).
*   **FlatSat (`503342353230000E`)** acts as the **Satellite** (powered autonomously).

#### Step 1: Flash CatSniffer with Ground Station Firmware
The CatSniffer requires Ground Station firmware compiled with its specific SX1262 LoRa pin mapping (RESET=GP24, BUSY=GP4, DIO1=GP5):
1. In `flat-sat-fw-interno/flatsat/boards/rpi_pico.overlay`, change the pins for `sx1262_0` to:
   ```dts
   reset-gpios = <&gpio0 24 GPIO_ACTIVE_LOW>;
   busy-gpios  = <&gpio0 4  GPIO_ACTIVE_HIGH>;
   dio1-gpios  = <&gpio0 5  GPIO_ACTIVE_HIGH>;
   ```
2. Build the Ground Station firmware (`FLATSAT_ROLE_GS` role):
   ```bash
   export ZEPHYR_BASE=/home/omaro/zephyr-workspace/zephyr
   /home/omaro/zephyr-workspace/.venv/bin/west build -d build_gs -p always -b rpi_pico -- -DOVERLAY_CONFIG=prj_gs.conf
   ```
3. Restore the original FlatSat overlay configurations in `rpi_pico.overlay`.
4. Put the CatSniffer in bootloader mode (e.g. by sending `reboot` via serial shell or holding its boot button) and copy `build_gs/zephyr/zephyr.uf2` to the mounted `RPI-RP2` drive.

#### Step 2: Power up the FlatSat (Satellite)
Power up the FlatSat board standalone (via a USB charger/power source or battery). It runs the default satellite firmware and automatically starts transmitting sensor/heartbeat telemetry over the air on 915 MHz.

#### Step 3: Run the Webapp and Connect
1. Connect the flashed CatSniffer to the PC via USB.
2. Start the ground station webapp:
   ```bash
   source .venv/bin/activate
   python -m webapp.app
   ```
3. Open `http://localhost:5000` in the browser, log in, and click **Scan USB** in the hardware panel.
4. Select the CatSniffer device serial number (`E661A897539C4732`) and click **Connect**.
5. Go to the dashboard/satellite views to see the over-the-air telemetry updates received from the FlatSat!

> **Linux USB permissions:** If the device is not detected, you may need to add a udev rule or run with appropriate permissions. See [Troubleshooting](#troubleshooting).

## Docker

```bash
docker compose up
```

Open `http://localhost:5000`. To use hardware mode, ensure the FlatSat is connected before starting the container.

See [docker-compose.yml](docker-compose.yml) for USB device mapping configuration.

## Architecture

```
browser  <->  webapp/ (Flask + SocketIO)  <->  core/ (protocol + serial)  <->  FlatSat USB
                 |
              db/ (SQLite)
```

### Core Library (`core/`)

| Module             | Purpose                                           |
|--------------------|---------------------------------------------------|
| `ccsds.py`         | CCSDS Space Packet encoder/decoder with SDLS       |
| `serial_manager.py`| USB device discovery by VID:PID                    |
| `device.py`        | Threadsafe serial wrapper for 3 CDC endpoints      |
| `telemetry.py`     | Telemetry payload decoder (Heartbeat, BME280, LIS2DH) |
| `telecommand.py`   | Telecommand frame builder with SDLS encryption     |
| `state.py`         | Ground station state machine (IDLE/HARDWARE/SIMULATED) |
| `shell_parser.py`  | Firmware shell response parsers                    |
| `constants.py`     | Opcode definitions and protocol constants          |

### Web Application (`webapp/`)

| Module          | Purpose                                    |
|-----------------|--------------------------------------------|
| `app.py`        | Flask routes, API endpoints, SocketIO      |
| `auth.py`       | Authentication (MD5 + base64 tokens)       |
| `db.py`         | SQLite schema and helpers                  |
| `radio_bridge.py`| Serial bridge for send operations         |
| `seed.py`       | Database seed data                         |
| `config.py`     | Flask configuration                        |

### Database (`db/`)

SQLite with tables: `users`, `telemetry`, `radio_config`, `secrets`, `logs`. Created automatically on first run.

## Webapp Pages

- **Dashboard** (`/dashboard`) — Live telemetry via WebSocket, hardware control (scan/connect/simulate), telecommand panel
- **Satellite** (`/satellite`) — Satellite status, battery monitor, LoRa radio config (R0/R1), sensor readout, device controls
- **Config** (`/config`) — Radio configuration with DB persistence
- **Logs** (`/logs`) — System log viewer

## Configuring the Device via the Satellite Menu

The **Satellite** page (`/satellite`) is the central control hub for the connected hardware. It dynamically adapts based on whether the connected device is acting as a **Ground Station** or a **Satellite** (highlighted by the neon role badge next to the page heading).

### 1. Flight States (Flight Panel)
Controls the operational/vessel state of the satellite:
* **Idle:** Suspends all telemetry and heartbeat transmissions. **Always set the flight state to Idle before reconfiguring radios** to prevent RF transmission collision or interference during commands.
* **Nominal:** Standard operational state. The satellite periodically reads sensor data and transmits telemetry packets over RF.
* **Safe:** Low-power safety state. Automatically entered if battery drops below `3000mV`. Telemetry rates are reduced.
* **Debug:** High-speed development/testing state. Telemetry is sent at an accelerated rate.

### 2. Device Modes (Mode Panel)
Sets the operating mode/role of the connected board:
* **Mission:** Configures the local board to act as the **Satellite**. The Neopixel heartbeat blinks **Green** (slow blink in stream mode).
* **Ground Station:** Configures the local board to act as the **Ground Station**. The Neopixel heartbeat blinks **Blue** (fast blink in command/listen mode).
* **TinyGS:** Switches the board to TinyGS receiver mode to spoof/intercept satellite downlinks.

### 3. Active Radio Selector
Configures how the board uses its physical LoRa transceivers (on 2-radio FlatSat boards):
* **Dual (TX: R1, RX: R0) [Default]:** Operates in full duplex loopback on a single board (transmitting commands on Radio 1 and receiving telemetry on Radio 0).
* **Radio 0 (CDC0):** Forces all operations onto the primary transceiver (Radio 0).
* **Radio 1 (CDC1):** Forces all operations onto the secondary transceiver (Radio 1).

### 4. Dynamic Radio Configuration
Depending on the role of the connected board and the active radio selection, the page dynamically displays only the relevant radio panel:
* **Ground Station Mode / Radio 0:** Displays **Local Radio 0** configuration (for tuning the telemetry receiver frequency, SF, BW, and power).
* **Satellite Mode / Radio 1:** Displays **Local Radio 1** configuration (for tuning the telemetry transmitter frequency, SF, BW, and power).
Click **Apply** to transmit configuration changes to the device.

### 5. TinyGS Spoofing Profiles
Emulates downlinks from real satellites in orbit. Select a profile in the dropdown and click **Spoof**:
* **Norbi:** Configures the radio to `436.703 MHz` (UHF).
* **FossaSat-2:** Configures the radio to `436.7 MHz` (UHF).
* **VR3X:** Configures the radio to `915.6 MHz` (ISM).
Click **Stop** to return to standard Mission mode.

## Configuring the Satellite (Remote Radio Configuration)

In hardware mode, you can update the LoRa parameters (frequency and power) of the remote satellite. The Ground Station transmits these configuration updates as CCSDS telecommand frames over RF first, and then applies the matching settings locally so the radio links remain synchronized.

### API Commands to Configure the Satellite

You can interact with these endpoints directly using a valid session cookie (e.g. from the Level 1 Session Forgery challenge):

* **Get current radio configuration (GET):**
  ```bash
  curl -H "Cookie: session_token=YWRtaW46YWRtaW46MTcwMDAwMDAwMA==" \
       "http://localhost:5000/api/satellite/lora_config?radio=R0"
  ```

* **Update remote satellite & local GS radio configuration (POST):**
  Specify the radio identifier (`R0` or `R1`) and the parameters to update:
  ```bash
  curl -X POST \
       -H "Content-Type: application/json" \
       -H "Cookie: session_token=YWRtaW46YWRtaW46MTcwMDAwMDAwMA==" \
       -d '{"radio": "R0", "frequency": 915500000, "sf": 8, "bw": 250, "power": 18}' \
       http://localhost:5000/api/satellite/lora_config
  ```

## Toolkit

Standalone scripts for interacting with FlatSat from the command line. Located in `toolkit/`.

| Script | Category | Purpose |
|--------|----------|---------|
| `ccsds_tools.py` | Protocol | CCSDS frame parser/builder, TM decoders, SDLS encrypt/decrypt |
| `forge_command.py` | Command | Telecommand forger — build and send TC frames |
| `crack_xor.py` | Crypto | Known-plaintext attack to recover XOR key |
| `crack_aes.py` | Crypto | AES key recovery via crypto oracle chosen-plaintext attack |
| `replay_capture.py` | RF | Capture and replay CCSDS frames over LoRa |
| `rf_scanner.py` | RF | LoRa frequency scanner — find the satellite's downlink |
| `frame_fuzzer.py` | Protocol | Mutate CCSDS fields to find parser bugs |
| `seq_predict.py` | Protocol | Predict sequence counters to bypass anti-replay |
| `fw_dumper.py` | Firmware | Dump memory via DIAG_MEMORY and analyze firmware binaries |
| `bus_sniffer.py` | Hardware | Decode SPI/I2C/UART captures from logic analyzers |
| `power_analysis.py` | Hardware | Simple/differential power analysis from oscilloscope traces |
| `neopixel_decode.py` | Mission | Decode covert channel data from Neopixel LED sequences |

```bash
cd toolkit

# Parse a captured frame
python ccsds_tools.py parse <hex>

# Build and send a PING command
python forge_command.py ping --send /dev/ttyACM1

# Scan for the satellite frequency
python rf_scanner.py quick /dev/ttyACM0 /dev/ttyACM1

# Fuzz the frame parser
python frame_fuzzer.py offline

# Capture and replay frames
python replay_capture.py capture /dev/ttyACM1 capture.json 30
python replay_capture.py replay /dev/ttyACM1 capture.json --modify-seq
```

## Tests

```bash
pytest
```

189 tests covering the core library, webapp routes, and vulnerability checks.

## Directory Structure

```
├── core/                  # Protocol and hardware library
│   ├── ccsds.py
│   ├── constants.py
│   ├── device.py
│   ├── serial_manager.py
│   ├── shell_parser.py
│   ├── state.py
│   ├── telecommand.py
│   └── telemetry.py
├── webapp/                # Flask web application
│   ├── app.py
│   ├── auth.py
│   ├── config.py
│   ├── db.py
│   ├── radio_bridge.py
│   ├── seed.py
│   ├── static/
│   │   ├── css/           # Stylesheets
│   │   └── js/            # Client-side JavaScript
│   └── templates/         # Jinja2 HTML templates
├── toolkit/               # Standalone attack/analysis scripts (12 tools)
│   ├── ccsds_tools.py     # CCSDS protocol library
│   ├── forge_command.py   # TC frame forger
│   ├── crack_xor.py       # XOR key cracker
│   ├── crack_aes.py       # AES oracle attack
│   ├── replay_capture.py  # Frame capture/replay
│   ├── rf_scanner.py      # Frequency scanner
│   ├── frame_fuzzer.py    # Protocol fuzzer
│   ├── seq_predict.py     # Sequence predictor
│   ├── fw_dumper.py       # Memory dumper
│   ├── bus_sniffer.py     # Bus traffic decoder
│   ├── power_analysis.py  # Power trace analysis
│   └── neopixel_decode.py # Covert channel decoder
├── tests/                 # pytest test suite
├── db/                    # SQLite database files (auto-created)
├── docs/                  # Design specs and plans
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Flashing Firmware to Different Boards

The firmware is built using **Zephyr RTOS**, which separates hardware definitions (Device Tree) from application logic. To port the firmware to a different hardware board, follow these three steps:

### 1. Configure the Target Board
When running the `west build` command, specify your target board using the `-b` flag:
```bash
# Example: Build for a Sparkfun Pro Micro RP2040
west build -s . -b sparkfun_pro_micro_rp2040 -- -DOVERLAY_CONFIG=prj_gs.conf
```
Zephyr supports many boards out of the box (e.g., `rpi_pico`, `adafruit_kb2040`, etc.).

### 2. Map Peripherals via Device Tree Overlay (`.overlay`)
Each board has its own physical wiring. Create or modify the overlay file corresponding to your board in `boards/<target_board>.overlay` (e.g., `boards/sparkfun_pro_micro_rp2040.overlay`) to match its pin mapping.

Make sure the following device tree aliases point to the correct radio node definitions:
*   `lora0 = &sx1262_0;` (Mapped to the first physical radio chip)
*   `lora1 = &sx1262_1;` (Mapped to the second radio chip, only needed for Dual-Radio role)

Ensure the SPI nodes, Chip Select (CS) GPIOs, and radio control pins are mapped correctly for your board:
```dts
&spi0 {
    status = "okay";
    cs-gpios = <&gpio0 17 GPIO_ACTIVE_LOW>; // Match your CS pin

    sx1262_0: sx1262@0 {
        compatible = "semtech,sx1262";
        reg = <0>;
        spi-max-frequency = <1000000>;
        reset-gpios = <&gpio0 24 GPIO_ACTIVE_LOW>; // Reset pin
        busy-gpios  = <&gpio0 4  GPIO_ACTIVE_HIGH>; // Busy pin
        dio1-gpios  = <&gpio0 5  GPIO_ACTIVE_HIGH>; // DIO1 pin
    };
};
```

### 3. Select the Role (Kconfig)
Choose the appropriate role configuration by specifying the overlay config flag (`-DOVERLAY_CONFIG`):
*   **Ground Station Only (`prj_gs.conf`):** Sets `CONFIG_FLATSAT_ROLE_GS=y`. Initializes only Radio 0 (CDC0) and Shell (CDC2). Best for boards with a single physical radio (like CatSniffer).
*   **Satellite Only (`prj_sat.conf`):** Sets `CONFIG_FLATSAT_ROLE_SAT=y`. Initializes only Radio 0, reads sensors, and transmits telemetry autonomously.
*   **Dual Radio (`prj.conf` / `prj_dual.conf`):** Sets `CONFIG_FLATSAT_ROLE_DUAL=y`. Mosaics both Radio 0 and Radio 1, and auto-detects Satellite/GS modes at boot based on the presence of onboard I2C sensors.

## Troubleshooting

### FlatSat not detected on Linux

Add a udev rule for the device:

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1209", ATTR{idProduct}=="babc", MODE="0666"' | sudo tee /etc/udev/rules.d/99-pwnsat.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Reconnect the FlatSat after applying the rule.

### FlatSat not detected on Windows
*   **Driver Issue:** Windows normally loads the default USB CDC Virtual Serial Port driver automatically. If not detected, check Device Manager to see if the device shows up under "Ports (COM & LPT)".
*   **No udev rule needed:** You do not need any special udev rules on Windows.

### Script Execution Policy in PowerShell (Windows)
If activating the virtual environment via `.venv\Scripts\Activate.ps1` fails with an execution policy error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```
Or use a standard Command Prompt (CMD) and activate using:
```cmd
.venv\Scripts\activate.bat
```

### Port 5000 already in use

*   **Linux:** Kill the existing process or change the port in `webapp/app.py`.
*   **Windows:**
    ```cmd
    # Find the PID using port 5000:
    netstat -ano | findstr :5000
    # Taskkill the process:
    taskkill /PID <PID> /F
    ```
*   **macOS (AirPlay Receiver Conflict):** By default, macOS Monterey and later uses port 5000 for the AirPlay Receiver service. You can disable this conflict in *System Settings -> General -> AirDrop & AirPlay -> Turn off "AirPlay Receiver"*, or change the listening port to `5001` in `webapp/app.py`.

### Python/Pip Commands Not Recognized (macOS)
If the terminal indicates that `python` or `pip` is not recognized after installing Python on macOS, you should use `python3` and `pip3` instead.
To create permanent shortcuts/aliases in your shell:
```bash
echo 'alias python="python3"' >> ~/.zshrc
echo 'alias pip="pip3"' >> ~/.zshrc
source ~/.zshrc
```

### Virtual Environment (.venv) Creation Fails (macOS)
If running `python3 -m venv .venv` executes without error but doesn't correctly create the activation script (e.g. `.venv/bin/activate` is missing, which is a known issue on some macOS setups or newer Python versions), use `virtualenv` instead:
1. Install `virtualenv` globally:
   ```bash
   pip3 install virtualenv
   ```
2. Create the environment:
   ```bash
   virtualenv .venv
   ```
3. Activate it:
   ```bash
   source .venv/bin/activate
   ```

### Database issues

Delete `db/telemetry.db` and restart — it will be recreated with seed data automatically.

### Webapp hangs during telecommand transmission (Single-Radio hardware like CatSniffer)

If the web application hangs in a `pending` state when sending a telecommand (like a PING or a command via the API), and your board physically only has one radio chip:
1. **Unplug and replug the USB cable** of the board to reset the hung virtual COM port driver in your OS.
2. Set the `FLATSAT_SINGLE_RADIO` environment variable to `1` before starting the application:
   * **Linux/macOS:** `export FLATSAT_SINGLE_RADIO=1`
   * **Windows (PowerShell):** `$env:FLATSAT_SINGLE_RADIO="1"`
   * **Windows (CMD):** `set FLATSAT_SINGLE_RADIO=1`
3. Restart the webapp.



