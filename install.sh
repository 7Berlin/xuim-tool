#!/bin/bash
set -e

echo "📦 Installing requirements..."
apt update && apt install -y python3 python3-venv git

echo "📥 Cloning repository..."
rm -rf /opt/xuim
git clone https://github.com/7berlin/xuim-tool /opt/xuim

echo "🐍 Creating virtual environment..."
python3 -m venv /opt/xuim/venv

echo "📦 Installing Python dependencies inside venv..."
/opt/xuim/venv/bin/pip install --upgrade pip
/opt/xuim/venv/bin/pip install tabulate

chmod +x /opt/xuim/xuim.py
chmod +x /opt/xuim/uninstall.sh

echo "⚙️ Creating xuim command..."
cat <<'EOF' >/usr/bin/xuim
#!/bin/bash
exec /opt/xuim/venv/bin/python /opt/xuim/xuim.py "$@"
EOF

chmod +x /usr/bin/xuim

echo "✅ Installation completed."
echo "🚀 Running xuim now..."
xuim
