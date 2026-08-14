# FlatSat Ground Station Makefile

PYTHON ?= python3
PIP ?= pip

.PHONY: all help install build test clean

all: build

help:
	@echo "FlatSat Ground Station CLI Makefile"
	@echo "Usage:"
	@echo "  make install    Install flatsat as a python package (pip install -e .)"
	@echo "  make build      Compile standalone binary using PyInstaller"
	@echo "  make test       Run automated pytest test suite"
	@echo "  make clean      Remove build artifacts"

install:
	@echo "[*] Installing flatsat package..."
	$(PIP) install -e .

build:
	@echo "[*] Compiling flatsat standalone binary with PyInstaller..."
	bash ./compile.sh

test:
	@echo "[*] Running tests..."
	$(PYTHON) -m pytest tests/

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
