#!/usr/bin/env bash
# =============================================================================
#  install.sh — Asymmetric Strike Team Installer
#
#  Installs the grind CLI tool and optional background service.
#
#  Usage:
#    ./install.sh              # CLI only
#    ./install.sh --service    # CLI + LaunchAgent background service
#    ./install.sh --uninstall  # Remove everything
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_SRC="$PROJECT_DIR/bin/grind"
BIN_DST="$HOME/.local/bin/grind"
PLIST_SRC="$PROJECT_DIR/com.asymmetric-strike-team.grind.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.asymmetric-strike-team.grind.plist"
SERVICE_NAME="com.asymmetric-strike-team.grind"
LOG_DIR="$PROJECT_DIR/logs"

install_cli() {
    echo "==> Installing grind CLI..."
    mkdir -p "$HOME/.local/bin"

    if [ -f "$BIN_SRC" ]; then
        ln -sf "$BIN_SRC" "$BIN_DST"
        chmod +x "$BIN_SRC"
        echo "    Linked: $BIN_DST → $BIN_SRC"
    else
        echo "    ERROR: $BIN_SRC not found" >&2
        return 1
    fi

    if echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
        echo "    ✓ $HOME/.local/bin is in PATH"
    else
        echo "    ⚠  Add to your ~/.zshrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

install_service() {
    echo "==> Installing LaunchAgent service ($SERVICE_NAME)..."

    # Create log directory
    mkdir -p "$LOG_DIR"

    if [ ! -f "$PLIST_SRC" ]; then
        echo "    ERROR: $PLIST_SRC not found" >&2
        return 1
    fi

    cp "$PLIST_SRC" "$PLIST_DST"
    echo "    Plist: $PLIST_DST"

    # Load the service
    launchctl load "$PLIST_DST" 2>/dev/null || launchctl bootstrap gui/$(id -u) "$PLIST_DST"
    echo "    ✓ Service loaded (runs every 300s)"
    echo "    Logs: $LOG_DIR/"
}

uninstall() {
    echo "==> Uninstalling..."

    # Unload service
    if [ -f "$PLIST_DST" ]; then
        launchctl bootout gui/$(id -u) "$PLIST_DST" 2>/dev/null || true
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm -f "$PLIST_DST"
        echo "    ✓ Service unloaded"
    fi

    # Remove CLI
    if [ -L "$BIN_DST" ]; then
        rm "$BIN_DST"
        echo "    ✓ CLI removed"
    fi

    echo "    Done."
}

status() {
    echo "==> Grinding Wheel Status"

    if [ -x "$(command -v grind)" ]; then
        echo "  CLI:    ✓ installed at $(which grind)"
    else
        echo "  CLI:    ✗ not installed"
    fi

    if launchctl print "gui/$(id -u)/$SERVICE_NAME" 2>/dev/null | grep -q "path ="; then
        LAST_RUN=$(tail -1 "$LOG_DIR/grind-stdout.log" 2>/dev/null || echo "no logs yet")
        if [ -f "$PLIST_DST" ]; then
            echo "  Service: ✓ plist installed (runs every 300s, exits between turns)"
            echo "  Last output: $LAST_RUN"
        else
            echo "  Service: ✗ not loaded"
        fi
    else
        echo "  Service: ✗ not loaded"
    fi

    echo ""
    echo "To run manually: grind --once"
    echo "To tail logs:    tail -f $LOG_DIR/grind-stdout.log"
}

# --- Main ---

case "${1:-cli}" in
    cli|--cli)
        install_cli
        ;;
    service|--service)
        install_cli
        install_service
        ;;
    uninstall|--uninstall)
        uninstall
        ;;
    status|--status)
        status
        ;;
    *)
        echo "Usage: $0 [--cli|--service|--uninstall|--status]"
        echo ""
        echo "  (default)   Install CLI only"
        echo "  --service   Install CLI + LaunchAgent background service"
        echo "  --uninstall Remove all installed components"
        echo "  --status    Check installation status"
        exit 1
        ;;
esac
