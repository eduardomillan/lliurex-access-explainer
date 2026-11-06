# Testing

Everything here runs on the ThinkPad test machine only. Nothing in this
project touches the 4-classroom pilot yet - see
[FUTURE-ANSIBLE-DEPLOYMENT.md](FUTURE-ANSIBLE-DEPLOYMENT.md).

## 0. Unit tests (no root, no N4D, no risk)

```bash
python3 -m pytest tests/ -q
```

Run this first, every time `n4d-plugin/AccessExplainer.py` changes.

## 1. Install just the plugin (no theme patch yet)

```bash
sudo ./scripts/install.sh --plugin-only
```

This copies the plugin into `/usr/share/n4d/python-plugins/` and its
config into `/etc/n4d/conf.d/`, then restarts `n4d.service` (safe - does
not affect the active graphical session).

## 2. Call the plugin directly, without touching the login screen

```bash
n4d-client -r call AccessExplainer explain_login_failure <test_username> es
```

Confirms the plugin actually responds before risking the login screen at
all. Try it with:
- A real username that exists and has no restrictions → expect the
  generic fallback message.
- A username with no account at all → still expect a safe message, never
  an error/exception back from N4D.

## 3. Local denial list, without touching any real domain account

```bash
# back up first
sudo cp -a /etc/lliurex-access-control /etc/lliurex-access-control.bak

# add a throwaway local test user to the deny list, through
# AccessControlManager's own XML-RPC API (not by hand-editing files)
n4d-client -r call AccessControlManager set_users_info '{"explainer-test-user": {"isLocked": true}}'

n4d-client -r call AccessExplainer explain_login_failure explainer-test-user es
# expect: the "local_user_denied" message from docs/MESSAGES.md

# clean up
n4d-client -r call AccessControlManager set_users_info '{}'
```

This exercises the Phase 1 priority-1 check without ever touching a real
student account.

## 4. Visual check of the patched greeter, without killing the active session

```bash
sddm-greeter --test-mode --theme /usr/share/sddm/themes/lliurex
```

Confirmed available on this machine. Opens the real theme in a window; it
does not replace the active session's greeter. Use this to visually
confirm the `Kirigami.InlineMessage` shows the new text instead of (or
before) "Login failed". A real `onLoginFailed` signal normally only fires
from an actual SDDM session, so this step mainly validates that the
patched QML loads and renders without errors - check its console output
for QML warnings/errors too.

## 5. The real thing, with a rollback plan ready

Only after steps 0-4 all look right:

1. Open a second virtual terminal (Ctrl+Alt+F2) and log in as root there.
   Keep this terminal open and have the rollback command typed out but
   **not yet executed**:
   ```bash
   /home/eduardo/lliurex-access-explainer/scripts/uninstall.sh && systemctl restart sddm
   ```
2. Back on the first VT, apply the full install (plugin + theme patch):
   ```bash
   sudo ./scripts/install.sh
   ```
3. Restart sddm for real:
   ```bash
   sudo systemctl restart sddm
   ```
4. At the login screen, deliberately fail a login (wrong password, or a
   locked test account from step 3) and confirm the new message appears.
5. If the greeter doesn't render, or login is impossible for any reason,
   switch to the second VT and run the rollback command immediately.

## 6. Full round-trip: install → verify → uninstall → verify clean

Before even considering the classroom pilot:

```bash
sudo ./scripts/install.sh
# steps 1-5 above

sudo ./scripts/uninstall.sh
sha256sum /usr/share/sddm/themes/lliurex/Main.qml
# must match sddm-theme-patch/versions.yml's sha256_pristine for the
# currently installed lliurex-sddm-theme version

sudo systemctl restart sddm
# confirm login still works exactly as it did before this project existed
```

Only once this full cycle has been run successfully, more than once, on
this ThinkPad, does it make sense to start planning the classroom pilot.
