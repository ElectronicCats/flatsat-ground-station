# PR: Major Refactor - Modular Architecture, Comprehensive CLI, Webapp Overhaul, and CTF Framework

## Summary
This PR introduces a complete architectural overhaul of the FlatSat Ground Station, transforming it from a monolithic codebase into a modular, well-tested platform.

---

## Key Changes

### 🏗️ Architecture & Modularity
- **New `modules/` structure**: Core logic (`modules/core/`), webapp (`modules/webapp/`), firmware tools, and utilities now organized as proper Python packages
- **Centralized `RadioBridge`** in `core/radio_bridge.py` shared between CLI and webapp for consistent RF handling
- **Click-based CLI** (`cli/`) replacing argparse with subcommands: `flight`, `sniff`, `replay`, `transmit`, `mode`, `config`, `completion`, `devices`, `status`, `sensors`, `identify`, `difficulty`, `reboot`, `color`

### 🖥️ Webapp Overhaul (`modules/webapp/`)
- Flask app with authentication, SQLite database, and REST API endpoints
- Real-time telemetry dashboard with WebSocket live updates
- Satellite control panel with dual-radio management
- CTF framework with level-aware challenges and flag delivery
- Role-based access control (operator vs admin)

### 📡 Protocol & Radio Improvements
- **SDLS protocol**: Auto-detection of remote satellite encryption difficulty from heartbeats
- **Dual-radio support**: Explicit radio addressing (`R0`/`R1` prefixes) to prevent misconfiguration
- **Mission mode fixes**: Correct radio mode configuration for satellite uplink/downlink
- **TX/RX serialization**: Lock-based radio transmit to prevent conflicts with telemetry reception

### 🪟 Windows & Serial Reliability
- Comprehensive Windows 11 serial I/O fixes (encoding, port detection, echo stripping, endpoint mapping)
- UTF-8 enforcement for CLI on Windows
- PowerShell wrapper fixes and Windows installer (NSIS + `.iss`)

### 🧪 Testing & Quality
- **40+ test files** covering CLI commands, webapp endpoints, CTF interoperability, edge cases, and integration
- Test matrix for SDLS difficulty levels and encrypt-then-CRC firmware

### 📦 Packaging & CI/CD
- Docker multi-stage build, docker-compose, `.dockerignore`
- Debian packaging (`packaging/debian/control`)
- Windows installer (PyInstaller spec + NSIS script)
- Shell completion install command (bash/zsh/fish)
- MIT license added

### 🛠️ Toolkit Expansion
- `flatsat_sniff.py/ps1` - RF frame capture
- `flatsat_spoof.py` - Frame replay/spoofing
- `forge_token.py` - CTF token generation
- `listen_radio.py` - Radio monitoring

### 📚 Documentation
- Restructured `README.md` with unified CTF guide
- Platform-specific setup instructions
- Removed legacy plans/specs directories

---

## Breaking Changes
- Webapp moved from `webapp/` to `modules/webapp/`
- CLI entry point changed from `flatsat_cli.py` to `flatsat` (Click-based)
- `RadioBridge` import path changed
- Default `connect()` no longer forces device role

## Migration Notes
- Update imports: `from modules.core import ...`
- Run `flatsat completion install` for shell tab completion
- Review `confFlatsat.sh` for new configuration options

---

## Commit Range
`92d97d..d27aa1` (113 commits, ~11,884 insertions, ~4,707 deletions)