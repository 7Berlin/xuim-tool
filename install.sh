#!/bin/bash
set -e

echo "📦 Installing requirements..."
apt update && apt install -y python3 python3-pip git
pip3 install tabulate

echo "📥 Cloning repository..."
git clone https://github.com/7berlin/xuim-tool /opt/xuim

chmod +x /opt/xuim/xuim.py

echo "⚙️ Creating xuim command..."
cat <<EOF >/usr/bin/xuim
#!/bin/bash
python3 /opt/xuim/xuim.py
EOF

chmod +x /usr/bin/xuim

echo "✅ Installation completed. Run with: xuim"

sudo xuim
