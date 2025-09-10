#!/bin/bash
set -e

echo "🗑 Removing X-UI Management Tool..."

rm -rf /opt/xuim
rm -f /usr/bin/xuim

echo "✅ X-UI Management Tool uninstalled successfully."
