#!/bin/bash
set -e

INSTALL_DIR="/opt/xuim"
BIN_FILE="/usr/bin/xuim"

echo "Uninstalling X-UI Management Tool..."

# Remove symlink
if [ -f "$BIN_FILE" ]; then
    rm -f "$BIN_FILE"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

echo "Uninstallation completed."
echo "You can install it with:"
echo "bash <(curl -s https://raw.githubusercontent.com/7berlin/xuim-tool/main/install.sh)"
