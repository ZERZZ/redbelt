#!/bin/bash
# RUN THIS IF ITS YOUR FIRST TIME, BE AWARE THAT IT WILL INSTALL DEPENDENCIES AND CREATE A VIRTUAL ENVIRONMENT
# MANUAL INSTALLATION INSTRUCTIONS ARE AVAILABLE IN README.md

set -e

cd "$(dirname "$0")"

VENV_DIR=".venv"

# Create the virtual environment if it doesn't exist yet
if [ ! -d "$VENV_DIR" ]; then
    echo "No virtual environment found. Creating one in $VENV_DIR ..."
    python3 -m venv --system-site-packages "$VENV_DIR"

    echo "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt..."
        pip install --upgrade pip
        pip install -r requirements.txt
    else
        echo "Warning: requirements.txt not found, skipping dependency install."
    fi
else
    echo "Virtual environment already exists. Activating..."
    source "$VENV_DIR/bin/activate"
fi

echo ""
echo "===== DEBUG INFO ====="
echo "[*] python3 path:      $(which python3)"
echo "[*] pip path:          $(which pip)"
echo "[*] DISPLAY:           $DISPLAY"
echo "[*] XDG_CURRENT_DESKTOP: $XDG_CURRENT_DESKTOP"
echo "[*] XDG_DATA_DIRS:     $XDG_DATA_DIRS"
echo "[*] XDG_SESSION_TYPE:  $XDG_SESSION_TYPE"

echo "[*] gi (PyGObject) import check:"
python3 -c "
try:
    import gi
    print('    gi OK ->', gi.__file__)
except ImportError as e:
    print('    gi MISSING ->', e)
"

echo "[*] pystray backend check:"
python3 -c "
try:
    import pystray
    print('    pystray backend module ->', pystray.Icon.__module__)
except ImportError as e:
    print('    pystray MISSING ->', e)
"
echo "======================="
echo ""

echo "Running program..."
python3 main.py