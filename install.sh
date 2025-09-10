#!/bin/bash
set -e

INSTALL_DIR="/opt/xuim"
BIN_FILE="/usr/bin/xuim"

echo "Installing X-UI Management Tool..."

# Install dependencies
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Installing..."
    apt-get update && apt-get install -y python3 python3-pip
fi

pip3 install tabulate --quiet

# Create installation directory
mkdir -p "$INSTALL_DIR"

# Copy xuim.py to installation directory
cp xuim.py "$INSTALL_DIR/xuim.py"
chmod +x "$INSTALL_DIR/xuim.py"

# Create symlink for easy execution
ln -sf "$INSTALL_DIR/xuim.py" "$BIN_FILE"

# Copy uninstall script
cp uninstall.sh "$INSTALL_DIR/uninstall.sh"
chmod +x "$INSTALL_DIR/uninstall.sh"

echo "Installation completed!"
echo "Run the tool with: xuim"

# Run the tool immediately after installation
"$BIN_FILE"
