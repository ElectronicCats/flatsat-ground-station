# FlatSat Ground Station Makefile
#
# There is ONE installer (flatsat_app.py install) and ONE binary
# (flatsat-gs). These targets are just shortcuts for it.
#
#   make app-build       Build the standalone binary (PyInstaller)
#   make app-install     Install the app inside the project (no sudo)
#   make app-uninstall   Remove it from the user profile
#   make test            Run the automated pytest suite
#   make clean           Remove build artifacts

VENV_PYTHON = $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

PYTHON ?= $(VENV_PYTHON)
APP = flatsat_app.py

.PHONY: all help app-build app-install app-uninstall test clean

all: help

help:
	@echo "FlatSat Ground Station Makefile"
	@echo "Usage:"
	@echo "  make app-build       Build the standalone app binary (dist/flatsat-gs)"
	@echo "  make app-install     Install the app inside the project (no sudo)"
	@echo "  make app-uninstall   Remove the installed app"
	@echo "  make test            Run automated pytest test suite"
	@echo "  make clean           Remove build artifacts"

app-build:
	@echo "[*] Building the standalone app binary..."
	PYTHON=$(PYTHON) bash ./compile_app.sh

app-install:
	@echo "[*] Installing FlatSat Ground Station into the project..."
	$(PYTHON) $(APP) install

app-uninstall:
	@echo "[*] Removing FlatSat Ground Station from the user profile..."
	$(PYTHON) $(APP) uninstall

test:
	@echo "[*] Running tests using $(PYTHON)..."
	$(PYTHON) -m pytest tests/

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
