# Multi-OS Guide: Installation, Testing, and Uninstallation

Technical guide to deploying, validating, and uninstalling the FlatSat Ground Station across **Linux**, **Windows**, and **macOS** natively, without Docker or virtual machines.

---

## 1. System Architecture and Registered Commands

The installation executes entirely in user space (requiring no root or administrator privileges) and exposes three unified tools on the system `PATH`:

| Command | Primary Function | Default Operational Mode |
|---|---|---|
| `flatsat` | Interactive command-line interface (20+ subcommands). | Direct serial or Web REST via `-w` |
| `flatsat-web` | Flask + WebSocket server launching the web dashboard. | `http://127.0.0.1:5000` |
| `flatsat-gs` | Lifecycle manager (`install`, `uninstall`, `doctor`, `version`). | Diagnostic and installation manager |

```text
                       ┌──────────────────────────────┐
                       │      flatsat-gs install      │
                       └──────────────┬───────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
     [Linux / CachyOS]          [Windows 10/11]            [macOS]
   ~/.local/bin/flatsat     %LOCALAPPDATA%\...\bin   ~/.local/bin/flatsat
   .desktop in applications  Start Menu shortcuts    .command on Desktop
```

---

## 2. Step-by-Step: Linux (Ubuntu, Debian, Fedora, Arch / CachyOS)

### Prerequisites
- Access permissions to USB serial endpoints (`/dev/ttyACM*`).
- Optional: Python 3.10+ (only when building from source; standalone binary requires no host Python).

### Step 1: Configure USB Serial Permissions (One-Time Setup)
1. Add the current user to the serial device groups:
   ```bash
   sudo usermod -aG dialout,uucp $USER
   ```
2. Install FlatSat udev rules to establish stable `/dev/flatsat/` symlinks and avoid modem-manager conflicts:
   ```bash
   sudo cp scripts/flatsat-udev.rules /etc/udev/rules.d/99-flatsat.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
3. Log out and log back in to apply group changes.

### Step 2: Installation
Select one of the two methods:

* **Option A (Standalone PyInstaller Binary - Recommended)**:
  ```bash
  # Compile locally (if needed):
  chmod +x compile_app.sh && ./compile_app.sh
  
  # Install into user profile:
  ./dist/flatsat-gs install
  ```

* **Option B (From Source with Virtual Environment)**:
  ```bash
  python3 flatsat_app.py install
  ```

*Result*: Executables are copied to `<project>/flatsat-gs/bin/`, symlinks are created in `~/.local/bin/`, and desktop files are added to `~/.local/share/applications/`.

### Step 3: Operational Verification

1. **Environment and Permission Diagnostic**:
   ```bash
   flatsat doctor
   ```
   *Expected Output*: Verified udev permissions with accessible `/dev/ttyACM0..2` endpoints in green.

2. **Hardware Detection**:
   ```bash
   flatsat devices
   ```
   *Expected Output*: Device table displaying USB serial numbers and `HEALTHY` operational state.

3. **Telemetry and Sensor Readings**:
   ```bash
   flatsat status
   flatsat sensors
   ```

4. **Concurrent Web and CLI Verification**:
   - Terminal 1: Launch the web dashboard:
     ```bash
     flatsat web --port 5000
     ```
   - Terminal 2: Query the station over the REST API without port locking conflicts:
     ```bash
     flatsat -w status
     flatsat -w sensors
     ```

5. **CTF Attack Suite Execution**:
   With the webapp active at `http://localhost:5000`:
   ```bash
   .venv/bin/python toolkit/run_individual_attack.py
   # Or run the complete automated exploitation chain:
   .venv/bin/python toolkit/exploit_demo.py
   ```

### Step 4: Clean Uninstallation
To remove all installed executables, symlinks, shortcuts, and PATH entries:
```bash
flatsat-gs uninstall
```

---

## 3. Step-by-Step: Windows (Windows 10 and Windows 11)

### Prerequisites
- USB CDC ACM drivers (native in Windows 10 build 1703+ and Windows 11).
- Disable Microsoft Store execution aliases if conflicting (*Settings → Apps → Advanced app settings → App execution aliases → Toggle off Python*).

### Step 1: Installation
Open **PowerShell** or **Command Prompt (CMD)** in the project directory:

* **Option A (Native Windows Launcher)**:
  ```cmd
  run.cmd install
  ```

* **Option B (Standalone Binary)**:
  ```powershell
  .\dist\flatsat-gs.exe install
  ```

* **Option C (From Python)**:
  ```powershell
  py -3 flatsat_app.py install
  ```

*Result*: Registers `flatsat-gs\bin` in the user PATH via the registry (`HKCU\Environment`), creates Start Menu shortcuts in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\`, and configures shims in `%LOCALAPPDATA%\Microsoft\WindowsApps`.

### Step 2: Operational Verification
Open a new terminal window to refresh the user PATH:

1. **System Diagnostic**:
   ```cmd
   flatsat doctor
   ```

2. **Device Detection**:
   ```cmd
   flatsat devices
   ```

3. **Status and Sensor Queries**:
   ```cmd
   flatsat status
   flatsat sensors
   ```

4. **Web and Concurrent CLI Mode**:
   - Terminal 1: `flatsat web`
   - Terminal 2: `flatsat -w status`

5. **CTF Exploitation Testing**:
   ```cmd
   python toolkit\run_individual_attack.py
   ```

### Step 3: Clean Uninstallation
```cmd
flatsat-gs uninstall
```
*Result*: Removes registry PATH entries, Start Menu shortcuts, and the `flatsat-gs` installation directory.

---

## 4. Step-by-Step: macOS (Intel x86_64 and Apple Silicon M1-M4)

### Prerequisites
- Python 3.10+ installed via Homebrew (`brew install python`) or python.org installer.
- Functional USB data cable for `/dev/cu.usbmodem*` detection.

### Step 1: Installation
Open **Terminal.app** in the project directory:

* **Option A (Standalone Binary)**:
  ```bash
  ./dist/flatsat-gs install
  ```

* **Option B (From Python)**:
  ```bash
  python3 flatsat_app.py install
  ```

*Result*: Deploys binaries to `flatsat-gs/bin/`, symlinks into `~/.local/bin/`, and generates a `FlatSat Ground Station.command` shortcut on the Desktop.

### Step 2: Operational Verification

1. **Serial Endpoint Diagnostic**:
   ```bash
   flatsat doctor
   ```

2. **Device Inspection**:
   ```bash
   flatsat devices
   ```

3. **Telemetry Readings**:
   ```bash
   flatsat status
   flatsat sensors
   ```

4. **Web and CLI Concurrent Mode**:
   - Terminal 1: `flatsat web --port 5001`
   - Terminal 2: `flatsat -w --web-url http://127.0.0.1:5001 status`

5. **CTF Attacks**:
   ```bash
   python3 toolkit/run_individual_attack.py
   ```

### Step 3: Clean Uninstallation
```bash
flatsat-gs uninstall
```

---

## 5. Command Equivalence Matrix

| Action | Linux | Windows | macOS |
|---|---|---|---|
| **Build Binary** | `./compile_app.sh` | `run.cmd build` | `./compile_app.sh` |
| **Install** | `./dist/flatsat-gs install` | `run.cmd install` | `./dist/flatsat-gs install` |
| **Diagnostic** | `flatsat doctor` | `flatsat doctor` | `flatsat doctor` |
| **List Devices** | `flatsat devices` | `flatsat devices` | `flatsat devices` |
| **Read Status** | `flatsat status` | `flatsat status` | `flatsat status` |
| **Read Sensors** | `flatsat sensors` | `flatsat sensors` | `flatsat sensors` |
| **Web Dashboard** | `flatsat web` | `flatsat web` | `flatsat web --port 5001` |
| **CLI via Web API** | `flatsat -w status` | `flatsat -w status` | `flatsat -w status` |
| **Individual Attacks** | `python toolkit/run_individual_attack.py` | `python toolkit\run_individual_attack.py` | `python3 toolkit/run_individual_attack.py` |
| **Full CTF Chain** | `python toolkit/exploit_demo.py` | `python toolkit\exploit_demo.py` | `python3 toolkit/exploit_demo.py` |
| **Uninstall** | `flatsat-gs uninstall` | `flatsat-gs uninstall` | `flatsat-gs uninstall` |

---

## 6. Troubleshooting Common Issues

### Issue: Permission Denied on `/dev/ttyACM*` (Linux)
- **Cause**: User lacks `dialout` or `uucp` group membership.
- **Fix**: `sudo usermod -aG dialout,uucp $USER` and log back in.

### Issue: `Device or resource busy` during CLI execution
- **Cause**: Webapp is holding the serial endpoints open.
- **Fix**: Use web mode: `flatsat -w status` or `flatsat --web-url http://127.0.0.1:5000 status`.

### Issue: `flatsat: command not found` after installation
- **Linux/macOS**: Export `~/.local/bin` to PATH in `~/.bashrc` or `~/.zshrc`:
  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```
- **Windows**: Reopen the console session to refresh registry PATH updates.
