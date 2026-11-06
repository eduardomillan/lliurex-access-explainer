# Changelog

All notable changes to this project are documented here, following
roughly the [Keep a Changelog](https://keepachangelog.com/) format.
`VERSION` at the repo root is the single source of truth for the
current version, also shown on the login screen's pilot-active label.

## [1.0.4] - version bump only

No functional change - only the pilot-active label's version string
(`v1.0.3` -> `v1.0.4`).

## [1.0.3] - tested on 172.28.222.128 and 172.28.222.245

### Added
- Status bar now shows the machine's physical Ethernet/Wi-Fi IP
  addresses (`AccessExplainer.get_network_info()`), next to the
  existing hostname label. Loopback and virtual interfaces
  (Docker, VirtualBox, bridges, veth, ...) are excluded by checking
  for a real `/sys/class/net/<iface>/device` symlink, not by matching
  interface names.
- `docs/ISSUES.md` rewritten as a GitHub-label-style tracker (`bug`,
  `enhancement`, `help wanted`) for every other open item: the
  unresolved font-size bug, the English-only transient message,
  Phase 2, the `.deb` package, the Ansible stage, and a pedagogical
  review of the message wording.
- `.deb` packaging scaffold (`debian/control`, `changelog`, `rules`,
  `postinst`/`prerm`/`postrm`, `copyright`, `source/format`). Maintainer
  scripts call `scripts/install.sh`/`uninstall.sh` directly instead of
  duplicating their logic. Not yet built or tested end to end.

## [1.0.2] - tested

### Added
- The login-failure message now auto-hides after a configurable delay
  (`AccessExplainer.get_display_seconds()`, default 20s, overridable
  via `/etc/lliurex-access-explainer/display_seconds.conf` without
  re-patching `Main.qml`).
- The message also clears immediately if the student edits the
  username or password field (`onTextChanged` on `txtUser`/`txtPass`).
- `showError()`/`showWarning()` both restart the auto-hide timer, so
  this applies to every message shown through them, not just
  `AccessExplainer`'s own.

## [1.0.0] - tested

### Added
- `AccessExplainer` N4D plugin: local deny-list checks (via
  `AccessControlManager`, read-only), `sssd`/backend/pam-log checks run
  in parallel, local-account detection (`getent -s files`), and
  distinguishing "unknown user" from "wrong password" by `pam_sss`'s
  own numeric code instead of unreliable localized text matching.
- `Main.qml` patch for `lliurex-sddm-theme`: shows the explanation in
  the existing `Kirigami.InlineMessage`, sized to its content instead
  of a clipping fixed height; a light-blue-then-mint-green-then-soft-blue
  background panel behind the login box; the login box and its fonts
  enlarged; a "pilot active" label showing the project version.
- `n4d-plugin/messages.py`: the full `en`/`es`/`ca` message catalog,
  kept in its own file, written for an average 14-year-old reading
  level. Each on-screen message ends with its category key in
  brackets (e.g. `[generic]`) as a pilot/debug aid.
- `scripts/install.sh`/`uninstall.sh`: version/sha256-checked,
  idempotent, backed-up installer for the plugin and the theme patch.
  Never restarts `sddm` automatically.
- Full test suite (`tests/test_access_explainer.py`), `docs/` covering
  architecture, both feature phases, the message catalog, risks,
  testing procedure, and Kirigami-specific notes.
- `diagnose/diagnose_login_wifigva.sh`: the original manual,
  post-incident diagnostic script this project's detection logic is
  ported from.

### Fixed (found live on real test machines before this version)
- `Qt.locale().name` was called as a method (`.name()`) instead of
  read as a property, throwing a `TypeError` that silently aborted the
  whole explanation flow.
- The message box's fixed `height: 32` clipped longer messages to only
  their tail end.
- `font.pointSize` scaling had no effect because the base theme's font
  is defined by pixel size (`pointSize` returns `-1` in that case) -
  switched to `font.pixelSize`.
- `_check_pam_log` matched the English substring `"user unknown"`,
  which real systems never actually log in any language - switched to
  matching `pam_sss`'s own numeric return code.
- Added a compatibility shim for `AccessControlManager` method names,
  which changed between `n4d-lliurex-access-control` 1.12.15
  (camelCase) and 1.12.16 (snake_case), found on a second test machine.
