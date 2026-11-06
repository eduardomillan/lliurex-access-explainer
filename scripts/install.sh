#!/usr/bin/env bash
#
# install.sh - manual installer for lliurex-access-explainer (Phase 1).
#
# This is the "no Ansible yet" installer used for local testing on this
# ThinkPad. See docs/FUTURE-ANSIBLE-DEPLOYMENT.md for the planned migration
# to Ansible roles once this cycle is validated by hand.
#
# What it does, in order (each step is idempotent and safe to re-run):
#   1. Installs the AccessExplainer N4D plugin (+ config) and restarts n4d.
#   2. Optionally patches Main.qml (lliurex-sddm-theme), after checking the
#      installed theme version and the sha256 of the file against
#      sddm-theme-patch/versions.yml. Makes a backup before touching it.
#      Never restarts sddm by itself - that kills the active session.
#
# Usage:
#   sudo ./scripts/install.sh            # plugin + theme patch
#   sudo ./scripts/install.sh --plugin-only   # only step 1
#   sudo ./scripts/install.sh --force         # patch even if the theme
#                                              # version is not in versions.yml
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="/var/backups/lliurex-access-explainer"
MAIN_QML="/usr/share/sddm/themes/lliurex/Main.qml"
N4D_PLUGIN_DIR="/usr/share/n4d/python-plugins"
N4D_CONF_DIR="/etc/n4d/conf.d"

PLUGIN_ONLY=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --plugin-only) PLUGIN_ONLY=1 ;;
        --force) FORCE=1 ;;
        -h|--help)
            sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must run as root (it writes to /usr/share/n4d and /usr/share/sddm)." >&2
    exit 1
fi

echo "== Step 1: AccessExplainer N4D plugin =="
install -m 0644 "$REPO_ROOT/n4d-plugin/AccessExplainer.py" "$N4D_PLUGIN_DIR/AccessExplainer.py"
install -m 0644 "$REPO_ROOT/n4d-plugin/messages.py" "$N4D_PLUGIN_DIR/messages.py"
install -m 0644 "$REPO_ROOT/n4d-plugin/AccessExplainer.json" "$N4D_CONF_DIR/AccessExplainer.json"
echo "  Installed $N4D_PLUGIN_DIR/AccessExplainer.py, $N4D_PLUGIN_DIR/messages.py and $N4D_CONF_DIR/AccessExplainer.json"

echo "  Restarting n4d.service (does not affect the active graphical session)..."
systemctl restart n4d.service
sleep 1
systemctl is-active --quiet n4d.service && echo "  n4d.service is active." || {
    echo "  WARNING: n4d.service is not active after restart. Check: journalctl -u n4d -n 50" >&2
}

if [[ $PLUGIN_ONLY -eq 1 ]]; then
    echo "--plugin-only requested, skipping the Main.qml patch."
    exit 0
fi

echo
echo "== Step 2: Main.qml patch (lliurex-sddm-theme) =="

installed_version="$(dpkg-query -W -f='${Version}' lliurex-sddm-theme 2>/dev/null || true)"
if [[ -z "$installed_version" ]]; then
    echo "  lliurex-sddm-theme does not seem to be installed. Skipping theme patch." >&2
    exit 1
fi
echo "  Installed lliurex-sddm-theme version: $installed_version"

read -r supported_sha_pristine supported_sha_patched <<<"$(python3 - "$REPO_ROOT/sddm-theme-patch/versions.yml" "$installed_version" <<'PYEOF'
import sys, yaml
path, version = sys.argv[1], sys.argv[2]
with open(path) as fd:
    data = yaml.safe_load(fd)
for entry in data.get("supported_versions", []):
    if entry.get("theme_version") == version:
        print(entry["sha256_pristine"], entry["sha256_patched"])
        break
PYEOF
)"

if [[ -z "${supported_sha_pristine:-}" ]] && [[ $FORCE -ne 1 ]]; then
    echo "  ERROR: theme version $installed_version is not in sddm-theme-patch/versions.yml." >&2
    echo "  Re-run with --force to patch anyway (review the patch manually first!)," >&2
    echo "  or regenerate versions.yml for this version (see its header comment)." >&2
    exit 1
fi

current_sha="$(sha256sum "$MAIN_QML" | awk '{print $1}')"
patched_sha="$(sha256sum "$REPO_ROOT/sddm-theme-patch/Main.qml.patched" | awk '{print $1}')"

if [[ "$current_sha" == "$patched_sha" ]]; then
    echo "  Main.qml is already patched (sha256 matches). Nothing to do."
    exit 0
fi

if [[ -n "${supported_sha_pristine:-}" ]] && [[ "$current_sha" != "$supported_sha_pristine" ]] && [[ $FORCE -ne 1 ]]; then
    echo "  ERROR: installed Main.qml does not match the known pristine sha256 for" >&2
    echo "  version $installed_version, and it is not already our patched version." >&2
    echo "  Refusing to overwrite an unknown state. Re-run with --force to override." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
backup_path="$BACKUP_DIR/Main.qml.orig-$installed_version"
if [[ ! -f "$backup_path" ]]; then
    cp "$MAIN_QML" "$backup_path"
    echo "  Backed up original to $backup_path"
else
    echo "  Backup already exists at $backup_path (not overwritten)."
fi

install -m 0644 "$REPO_ROOT/sddm-theme-patch/Main.qml.patched" "$MAIN_QML"
echo "  Installed patched Main.qml."
echo
echo "  NOT restarting sddm automatically (this would kill the active session)."
echo "  To apply the new greeter, when you are ready:"
echo "      sudo systemctl restart sddm"
echo "  Consider testing first with:"
echo "      sddm-greeter --test-mode --theme /usr/share/sddm/themes/lliurex"
