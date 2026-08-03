#!/usr/bin/env bash
# Installs i3x11wpl for the current user:
#   - creates a venv and installs dependencies into it
#   - symlinks bin/i3x11wpl into ~/.local/bin/i3x11wpl
#   - installs a .desktop entry into ~/.local/share/applications
#
# After this, `i3x11wpl` works from any terminal (as long as
# ~/.local/bin is on your PATH), and it shows up in app launchers.
set -euo pipefail

PROJECT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "Installing i3x11wpl from $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

echo "Installing dependencies..."
"$PROJECT_DIR/venv/bin/pip" install --quiet --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"

mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
chmod +x "$PROJECT_DIR/bin/i3x11wpl"
ln -sf "$PROJECT_DIR/bin/i3x11wpl" "$BIN_DIR/i3x11wpl"

sed "s|__EXEC__|$BIN_DIR/i3x11wpl|" "$PROJECT_DIR/i3x11wpl.desktop" \
    > "$DESKTOP_DIR/i3x11wpl.desktop"

echo
echo "Done."
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "NOTE: $BIN_DIR is not on your PATH. Add this to ~/.bashrc:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo "Run it with: i3x11wpl"
