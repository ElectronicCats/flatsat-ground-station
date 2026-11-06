# Building and Installing — FlatSat Ground Station

Complete guide for **Windows, Linux, and macOS**: requirements, building the
standalone executable, installation, verification, uninstallation, and troubleshooting.

---

## 1. Installation Targets

| Target | Description | Prerequisites |
|---|---|---|
| **Standalone Binary** | Single self-contained binary embedding Python runtime, Flask, pyserial, click. Zero host dependencies. | None |
| **From Source** | Source code + dedicated virtual environment configured in the project directory. | Python 3.9+ |

Both installation workflows deploy into the **project folder** (`flatsat-gs/`) and
register identical commands:

| Command | Purpose |
|---|---|
| `flatsat web` | Launch web dashboard and open browser |
| `flatsat doctor` | System diagnostic: environment, serial ports, shell aliases |
| `flatsat devices` | Enumerate connected boards and serial endpoints |
| `flatsat status` | Display firmware, mode, and radio status |
| `flatsat sensors` | Read real-time telemetry sensor values |
| `flatsat sniff -n 3` | Capture incoming CCSDS frames |
| `flatsat install` / `flatsat uninstall` | Install or uninstall application |
| `flatsat-web`, `flatsat-gs` | Umbrella command and dedicated web launcher aliases |

---

## 2. Requirements

| Component | Version | Notes |
|---|---|---|
| Python | 3.9 or higher | Windows: check *"Add Python to PATH"* during installation |
| pip | Bundled with Python | Prebuilt wheels available: **no C compiler required** |
| Disk Space | ~80 MB | Standalone binary (20 MB) or virtual environment (~60 MB) |
| Serial Ports | `dialout` group membership (Linux) | See Section 7 |

---

## 3. Windows

### 3.1 Building the Standalone Executable

```bat
cd C:\path\to\flatsat-ground-station
.\run.cmd build
```

Or invoke the build script directly:

```bat
.\build_app_windows.bat
```

> **PowerShell requires the `.\` prefix** for scripts located in the current directory.

Output binary: `dist\flatsat-gs.exe` (~20 MB).

The build script:
1. Reuses the project `.venv` when present for a lighter binary (~20 MB vs ~51 MB); otherwise falls back to `py -3` or `python`.
2. Installs PyInstaller automatically if absent.
3. Packages the application with custom branding icons.

### 3.2 Installation

```bat
dist\flatsat-gs.exe install
```

Or from source:

```bat
.\run.cmd install
```

### 3.3 Handling Application Control Policies

Corporate Windows Defender Application Control (Device Guard / AppLocker) may restrict unsigned binaries:

```text
'...\dist\flatsat-gs.exe' was blocked by your organization's Device Guard policy.
```

The installer detects this condition automatically and falls back gracefully to the Python-based installation:

```text
[!] Binary flatsat-gs.exe blocked by system security policy.
[!] Falling back to Python deployment: identical commands, identical functionality.
```

Commands remain identical across all deployments:

```bash
flatsat web
flatsat doctor
flatsat devices
flatsat status
flatsat sniff -n 3
```

### 3.4 Verification

```bat
flatsat version
flatsat devices
flatsat doctor
```

Open a **new terminal session** after installation to reload the user PATH.

---

## 4. Linux

### 4.1 System Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

No C compiler needed: all dependencies supply precompiled wheels.

### 4.2 Building the Standalone Binary

```bash
cd ~/path/to/flatsat-ground-station
./compile_app.sh
```

For an **AppImage** package:

```bash
./compile_app.sh --bundle
```

Requires `appimagetool` in PATH; falls back to a `.tar.gz` bundle if not found.

Output binary: `dist/flatsat-gs` (or `dist/flatsat-gs-x86_64.AppImage`).

### 4.3 Installation

```bash
./dist/flatsat-gs install
```

Or from source:

```bash
python3 flatsat_app.py install
```

Directory structure created:

```text
flatsat-gs/
├── bin/          # flatsat-gs, flatsat-web, flatsat
├── db/           # Telemetry SQLite database
├── venv/         # Application virtual environment
└── install-manifest.json
```

Symlinks are linked into `~/.local/bin` (ensure this directory is on your PATH):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc   # or ~/.zshrc
source ~/.bashrc
```

### 4.4 Verification

```bash
flatsat version
flatsat devices
flatsat doctor
```

---

## 5. macOS

### 5.1 Prerequisites

```bash
# Using Homebrew (https://brew.sh)
brew install python@3.11
```

### 5.2 Building the Standalone Binary

```bash
cd ~/path/to/flatsat-ground-station
./compile_app.sh
```

To build a `.app` bundle and `.dmg`:

```bash
./compile_app.sh --bundle
```

Outputs:
- `dist/flatsat-gs`: Standalone CLI binary
- `dist/FlatSat GS.app`: GUI clickable bundle
- `dist/FlatSatGS-<version>.dmg`: Distribution disk image

### 5.3 Installation

```bash
./dist/flatsat-gs install
```

Or copy the `.app` bundle to `~/Applications`:

```bash
cp -R "dist/FlatSat GS.app" ~/Applications/
```

### 5.4 Handling Port 5000 (AirPlay Receiver)

macOS Monterey and newer reserve port 5000 for AirPlay Receiver:

```bash
flatsat web --port 5001
# Or permanently via environment:
export FLATSAT_PORT=5001
```

### 5.5 Serial Port Permissions

*System Settings → Privacy & Security → Serial Ports* → Enable Terminal or your preferred shell app.

Verify with:

```bash
flatsat doctor
```

Endpoints appear as `/dev/cu.usbmodem*`.

---

## 6. Platform Comparison Matrix

| Feature | Windows | Linux | macOS |
|---|---|---|---|
| Build Command | `.\run.cmd build` | `./compile_app.sh` | `./compile_app.sh` |
| Extra Bundles | None | AppImage (`--bundle`) | `.app` + `.dmg` (`--bundle`) |
| Install Command | `dist\flatsat-gs.exe install` | `./dist/flatsat-gs install` | `./dist/flatsat-gs install` |
| Exposed Commands | `flatsat`, `flatsat-web`, `flatsat-gs` | Identical | Identical |
| Serial Permissions | Automatic CDC ACM | `dialout` group / udev | System privacy toggle |
| Default Web Port | 5000 | 5000 | 5001 (due to AirPlay) |

---

## 7. Serial Port Permissions (Linux)

The board exposes three CDC-ACM endpoints: **Radio 0**, **Radio 1**, and **Shell**.

Option A — Group Membership:

```bash
sudo usermod -aG dialout,uucp $USER
# Log out and log back in to apply
```

Option B — Udev Rules (Creates stable symlinks in `/dev/flatsat/` without requiring dialout):

```bash
sudo cp scripts/flatsat-udev.rules /etc/udev/rules.d/99-flatsat.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Validate permissions with `flatsat doctor`.

---

## 8. Uninstallation

```bash
flatsat-gs uninstall
```

Cleanly removes `<project>/flatsat-gs`, desktop shortcuts, restored user PATH, and shell completion scripts.

To preserve the telemetry database:

```bash
flatsat-gs uninstall --keep-data
```

---

## 9. Common Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| Command not recognized in PowerShell | Missing `.\` prefix | Use `.\run.cmd build` |
| Blocked by Device Guard policy | Corporate execution policy | Installer automatically falls back to Python mode |
| Missing Python 3.9+ | Python not on PATH or Store alias | Install official Python and select "Add to PATH" |
| Port 5000 in use (macOS) | AirPlay Receiver | Use `flatsat web --port 5001` |
| `flatsat devices` cannot find board | Serial permissions | Review Section 7 and run `flatsat doctor` |
| Webapp folder cannot be deleted on uninstall | Process still running | Terminate webapp process and retry uninstall |
