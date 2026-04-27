#!/bin/bash
set -e

echo "Installing shelltide..."

# Install Python dependencies
pip install ephem drawille --break-system-packages -q

# Get the directory where shelltide lives
SHELLTIDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a launcher script in /usr/local/bin
sudo tee /usr/local/bin/shelltide > /dev/null << SCRIPT
#!/bin/bash
python3 "$SHELLTIDE_DIR/shelltide.py" "\$@"
SCRIPT

sudo chmod +x /usr/local/bin/shelltide

echo "Done! Try: shelltide --location \"Bar Harbor, ME\""
