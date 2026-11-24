# Installation Guide — FlatSat Ground Station

Comprehensive guide to deploying the application (web dashboard + interactive CLI) across Windows, Linux,
and macOS **natively without Docker or virtual machines**, and performing clean uninstallation.

---

## 1. Installed Components

| Component | Description |
|---|---|
| Web Dashboard | Flask + WebSocket interface, live telemetry charts, board controls |
| Interactive CLI | `flatsat`: Unified shell exposing 20+ commands (devices, status, sniff, tc, attack...) |
| System Diagnostic | `flatsat doctor`: Hardware scan, udev rules check, and port locking analysis |
| Dependencies | Flask, Flask-SocketIO, simple-websocket, click, rich, pyserial, pycryptodome |

All dependencies provide prebuilt wheels: **no C compiler or build-essential required**.

---

## 2. Architecture: Single Installer, Unified Binary

FlatSat Ground Station features **one installer engine** and **one compiled binary**.
All invocation shortcuts delegate into it:

```text
                    ┌─────────────────────────────┐
                    │     flatsat_app.py install  │  ← Core installer engine
                    │    (or "flatsat-gs install")│
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
       flatsat-gs install                        run.cmd install
       (Standalone binary)                       (Windows auto-discovery)
```

No external setup scripts or system package managers required: the application manages its own lifecycle.

**Standard Layout:**

| Feature | Specification |
|---|---|
| Executables | `flatsat-gs` (umbrella tool), `flatsat-web` (dashboard), `flatsat` (CLI) |
| Installation Target | `<project>/flatsat-gs/bin` (or `%LOCALAPPDATA%\Programs\FlatSatGroundStation` / `~/.local/share/flatsat-ground-station`) |
| Desktop Shortcuts | Start Menu (Windows) · `~/.local/share/applications` (Linux) · Desktop `.command` (macOS) |
| User PATH | Executable directory registered in user PATH, cleanly restored upon uninstall |
| Uninstallation | `flatsat-gs uninstall` removes created files and restores PATH |

---

## 3. Platform Instructions

### 3.1 Windows 10 / 11

#### Pre-Check: Microsoft Store Python Alias
If invoking python displays:
```text
Python was not found; run without arguments to install from the Microsoft Store...
```
Disable execution aliases in:
*Settings → Apps → Advanced app settings → App execution aliases → Toggle off `python.exe` and `python3.exe`*.

Or use the bundled launcher which handles execution path resolution:

```bat
run.cmd                  :: Launch web dashboard
run.cmd cli              :: Launch interactive CLI
run.cmd install          :: Install permanently in user profile
```

#### Standalone Deployment
```bat
dist\flatsat-gs.exe install
```

---

### 3.2 Linux (Ubuntu, Debian, Fedora, Arch / CachyOS)

#### USB CDC Permissions
```bash
# 1. Install udev rules
sudo cp scripts/flatsat-udev.rules /etc/udev/rules.d/99-flatsat.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# 2. Add user to dialout and uucp groups
sudo usermod -aG dialout,uucp $USER
```

#### Installation
```bash
# From standalone binary
./dist/flatsat-gs install

# Or from source
python3 flatsat_app.py install
```

Symlinks are placed in `~/.local/bin/`. Ensure `~/.local/bin` is in `$PATH`:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

---

### 3.3 macOS (Intel and Apple Silicon)

```bash
# Install via Homebrew
brew install python@3.11

# Deploy
./dist/flatsat-gs install
```

> **Note on Port 5000**: macOS Monterey+ reserves port 5000 for AirPlay Receiver. Launch the dashboard on port 5001:
> ```bash
> flatsat web --port 5001
> ```

---

## 4. Verification and Health Checks

```bash
flatsat doctor       # Verify serial endpoints and udev permissions
flatsat devices      # Enumerate connected FlatSat boards
flatsat status       # Read active firmware version and telemetry state
```

---

## 5. Uninstallation

```bash
flatsat-gs uninstall
```

Completely removes installed binaries, Start Menu/desktop shortcuts, and restores the system user PATH without leaving residual configuration files.
