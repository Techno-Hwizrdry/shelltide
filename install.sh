#!/bin/bash
set -e

echo "Installing shelltide..."

# Install venv for Python3, if it is not already installed.
sudo apt update
sudo apt install python3-venv -y

# Get the directory where shelltide lives
SHELLTIDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SHELLTIDE_DIR/.venv"

if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

# Install Python dependencies
source "$VENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install -r "$SHELLTIDE_DIR/requirements.txt"
deactivate

# Create a launcher script in /usr/local/bin
sudo tee /usr/local/bin/shelltide > /dev/null << SCRIPT
#!/bin/bash
"$VENV_PATH/bin/python3" "$SHELLTIDE_DIR/shelltide.py" "\$@"
SCRIPT

sudo chmod +x /usr/local/bin/shelltide

echo ""
echo "Done! Try: shelltide --location \"Bar Harbor, ME\""
