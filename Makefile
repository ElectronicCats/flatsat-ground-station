# FlatSat Ground Station Makefile
# Mirrors CatSniffer / catnip Makefile architecture

VENV_PYTHON = $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
VENV_PIP = $(shell if [ -f .venv/bin/pip ]; then echo .venv/bin/pip; else echo pip; fi)

PYTHON ?= $(VENV_PYTHON)
PIP ?= $(VENV_PIP)
PREFIX ?= /usr/local
BIN_DIR = $(PREFIX)/bin

.PHONY: all help install build compile-install uninstall test clean

all: help

help:
	@echo "FlatSat Ground Station Makefile"
	@echo "Usage:"
	@echo "  make install         Install flatsat package and setup global symlink"
	@echo "  make compile-install Compile with PyInstaller and install globally"
	@echo "  make uninstall       Remove flatsat from the system"
	@echo "  make test            Run automated pytest test suite"
	@echo "  make clean           Remove build artifacts"

install:
	@echo "[*] Installing flatsat package using $(PIP)..."
	$(PIP) install -e .
	@echo "[*] Setting up global access (requires sudo)..."
	sudo bash ./scripts/install.sh $(shell which flatsat 2>/dev/null || echo "")

build: compile-install

compile-install:
	@echo "[*] Compiling flatsat standalone binary with PyInstaller..."
	PYTHON=$(PYTHON) bash ./compile.sh
	@echo "[*] Installing compiled binary to $(BIN_DIR)..."
	sudo cp dist/flatsat $(BIN_DIR)/flatsat || sudo cp dist/flatsat/flatsat $(BIN_DIR)/flatsat
	@echo "[+] Compiled binary installed to $(BIN_DIR)/flatsat"


uninstall:
	@echo "[*] Uninstalling flatsat package..."
	$(PIP) uninstall -y flatsat-ground-station
	@echo "[*] Removing global symlink/binary..."
	sudo rm -f $(BIN_DIR)/flatsat
	@echo "[+] Uninstalled successfully"

test:
	@echo "[*] Running tests using $(PYTHON)..."
	$(PYTHON) -m pytest tests/

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
