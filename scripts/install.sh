#!/bin/bash

# FlatSat Ground Station Post-Installation Script
# Purpose: Create a symlink in /usr/local/bin to ensure flatsat is accessible by sudo.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[*] FlatSat Post-Installation Hook${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run as root (sudo ./install.sh)${NC}"
  exit 1
fi

# Detect flatsat location
if [ -n "$1" ]; then
    FLATSAT_PATH="$1"
else
    FLATSAT_PATH=$(runuser -u "$SUDO_USER" -- which flatsat 2>/dev/null || which flatsat)
fi

if [ -z "$FLATSAT_PATH" ]; then
    # Try to find it in common user paths if not in PATH
    USER_HOME=$(eval echo "~$SUDO_USER")
    if [ -f "$USER_HOME/.local/bin/flatsat" ]; then
        FLATSAT_PATH="$USER_HOME/.local/bin/flatsat"
    fi
fi

if [ -z "$FLATSAT_PATH" ]; then
    echo -e "${RED}[-] Could not find 'flatsat' command. Please install the package first with 'pip install .'${NC}"
    exit 1
fi

echo -e "${BLUE}[*] Found flatsat at: $FLATSAT_PATH${NC}"

# Create symlink in /usr/local/bin (usually in sudo secure_path)
TARGET="/usr/local/bin/flatsat"

if [ -L "$TARGET" ] || [ -f "$TARGET" ]; then
    echo -e "${BLUE}[*] Removing existing flatsat link/binary in $TARGET...${NC}"
    rm -f "$TARGET"
fi

echo -e "${BLUE}[*] Creating global symlink...${NC}"
ln -s "$FLATSAT_PATH" "$TARGET"

echo -e "${GREEN}[+] flatsat is now globally accessible, including via sudo!${NC}"
echo -e "${GREEN}[+] Try running: sudo flatsat devices${NC}"
