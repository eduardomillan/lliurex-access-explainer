#!/usr/bin/env bash
#
# uninstall.sh - reverts everything scripts/install.sh did.
#
# Usage:
#   sudo ./scripts/uninstall.sh
#
set -euo pipefail

BACKUP_DIR="/var/backups/lliurex-access-explainer"
MAIN_QML="/usr/share/sddm/themes/lliurex/Main.qml"
N4D_PLUGIN="/usr/share/n4d/python-plugins/AccessExplainer.py"
N4D_MESSAGES="/usr/share/n4d/python-plugins/messages.py"
N4D_CONF="/etc/n4d/conf.d/AccessExplainer.json"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must run as root." >&2
    exit 1
fi

echo "== Removing AccessExplainer N4D plugin =="
if [[ -f "$N4D_PLUGIN" || -f "$N4D_MESSAGES" || -f "$N4D_CONF" ]]; then
    rm -f "$N4D_PLUGIN" "$N4D_MESSAGES" "$N4D_CONF"
    echo "  Removed $N4D_PLUGIN, $N4D_MESSAGES and $N4D_CONF"
    systemctl restart n4d.service
    echo "  Restarted n4d.service."
else
    echo "  Nothing to remove (plugin was not installed)."
fi

echo
echo "== Restoring Main.qml =="
installed_version="$(dpkg-query -W -f='${Version}' lliurex-sddm-theme 2>/dev/null || true)"
backup_path="$BACKUP_DIR/Main.qml.orig-$installed_version"

if [[ -f "$backup_path" ]]; then
    cp "$backup_path" "$MAIN_QML"
    echo "  Restored $MAIN_QML from $backup_path"
    echo
    echo "  NOT restarting sddm automatically. To apply:"
    echo "      sudo systemctl restart sddm"
else
    echo "  No backup found at $backup_path - either it was never patched here," >&2
    echo "  or the backup for this exact theme version ($installed_version) is missing." >&2
    echo "  Check $BACKUP_DIR manually before assuming Main.qml is clean." >&2
fi
