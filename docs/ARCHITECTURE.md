# Architecture

## Problem

On LliureX client machines in this school, students log in with their GVA
ID Digital / Microsoft account, authenticated against the `EDU.GVA.ES`
Active Directory domain through SSSD. Sometimes the account authenticates
correctly but the login is still rejected, and today the screen only shows
a generic "Login failed" - no hint for the student or whoever is helping
them in the classroom.

A manual diagnostic script already exists
(`diagnostico_login_wifigva.sh` on the admin's desktop) for an admin to run
**after** the fact. This project's goal is to surface that same kind of
explanation **on the login screen itself, at the moment of failure**, in
plain language.

## Two kinds of "phase" - don't mix them up

This project has two *feature* phases, and a separate, later *deployment*
stage. They are intentionally kept apart:

- **Phase 1** (feature): show a plain-language reason on any login
  failure. See [PHASE1.md](PHASE1.md).
- **Phase 2** (feature): cover finer-grained causes Phase 1 doesn't fully
  explain yet (which exact local list/mechanism denied access, explicit
  Kerberos errors from the central AD). See [PHASE2.md](PHASE2.md).
- **Future deployment stage** (Ansible, not a numbered phase): how this
  gets installed/uninstalled across a 4-classroom / ~75-machine pilot
  later on. **Deliberately postponed** - see
  [FUTURE-ANSIBLE-DEPLOYMENT.md](FUTURE-ANSIBLE-DEPLOYMENT.md). Right now
  everything is installed by hand with `scripts/install.sh`/`uninstall.sh`,
  only on this ThinkPad.

## Key finding that shapes the whole design

The LliureX SDDM theme (`/usr/share/sddm/themes/lliurex/Main.qml`, package
`lliurex-sddm-theme`) **already talks to N4D live during login**. It uses
the pattern:

```qml
N4D.Proxy {
    client: n4dLocal
    plugin: "SomePlugin"
    method: "some_method"
    onError: { ... }
    onResponse: { ... }
}
```

(verified: an existing block calling `WifiEduGva.get_active_connections`
in the real theme file). It already has `showError()`/`showWarning()`
helpers that fill a `Kirigami.InlineMessage` already present in the login
UI. Login failures are caught in:

```qml
Connections {
    target: sddm
    function onLoginFailed() {
        showError(i18nd("lliurex-sddm-theme","Login failed"));
        loginFrame.enabled = true;
        txtPass.text = "";
        txtPass.focus = true;
    }
}
```

`txtUser.text` is **not** cleared here (only `txtPass` is) - the attempted
username is still available at this point.

This means there is no need to touch PAM, or deal with SDDM's own PAM
conversation message signal (`informationMessage`), which the theme does
not even listen to today. A small N4D plugin plus a 3-piece patch to
`Main.qml` is enough, reusing exactly the pattern already used for WiFi.

Also verified directly on this machine:
- `n4d.service` runs as `User=root` - any plugin method, even one marked
  `anonymous` in its N4D config, executes with full root privileges.
- `AccessControlManager` (package `n4d-lliurex-access-control`) already
  manages `/etc/lliurex-access-control/{users-lists,groups-lists}` and
  exposes read methods (`get_users_info()`, `get_groups_info()`,
  `get_cdc_info()`, `is_access_denied_*`) that return an `isLocked` flag
  per user/group, and a CDC allow-list (`simple_allow_groups` in
  `sssd.conf`).
- `AccessControlManager.set_cdc_info()` runs
  `subprocess.run(['systemctl', 'restart', 'sssd'])` as a side effect.
  **`AccessExplainer` must only ever call the read (`get_*`/`is_*`)
  methods of `AccessControlManager`, never a write method.**

## Why no new PAM module

The obvious alternative design would add a new PAM module (the
`pam_script.so` pattern LliureX already uses for `hodor` in
`common-session`) to detect and report failure reasons from inside the
authentication stack itself. This project does **not** do that, because:

- `n4d-server` already runs as root and can read everything PAM would
  have exposed (journal, deny-lists, service status) without being part
  of the PAM stack.
- Adding a new step to `common-auth`/`common-account` on every client
  machine risks locking out login fleet-wide if the new step's control
  flag is wrong or the script misbehaves - for a benefit (a slightly more
  reliable detection of *which* PAM step failed) that doesn't justify that
  blast radius.

This is revisited only if real-world testing on the classroom pilot shows
that scanning the journal by time window is too unreliable (journald
rotation, too much delay between the failure and the student noticing).

## Risk: N4D packages are also system (apt) packages

Not just `lliurex-sddm-theme` can be updated under us by `apt` - so can
`n4d`, `n4d-lliurex-access-control` (which ships `AccessControlManager.py`),
and `qml-module-edupals-n4d`. An update to any of them could change method
signatures/behavior, or how `Main.qml` exposes `n4dLocal`/`N4D.Proxy`,
silently breaking `AccessExplainer` with no visible error until a student
sees a wrong message or a broken login. See [RISKS.md](RISKS.md) for the
concrete mitigations (version pinning for the theme, defensive method
lookups in the plugin, a pre-`apt upgrade` checklist).

## Repository layout

```
lliurex-access-explainer/
├── README.md
├── .gitignore
├── docs/                      # this file and the rest of the docs, in English
├── n4d-plugin/
│   ├── AccessExplainer.py
│   └── AccessExplainer.json
├── sddm-theme-patch/
│   ├── Main.qml.pristine      # exact copy of the theme file before patching
│   ├── apply_patch.py         # regenerates Main.qml.patched from the pristine copy
│   ├── Main.qml.patched       # generated - do not hand-edit, regenerate instead
│   ├── Main.qml.patch.txt     # human-readable diff, for reference
│   └── versions.yml           # supported lliurex-sddm-theme versions + sha256
├── scripts/
│   ├── install.sh
│   └── uninstall.sh
└── tests/
    └── test_access_explainer.py
```

No `roles/`, `inventories/`, or `playbooks/` yet - see
[FUTURE-ANSIBLE-DEPLOYMENT.md](FUTURE-ANSIBLE-DEPLOYMENT.md).

## Files outside this repo that are consulted or patched

- `/usr/share/sddm/themes/lliurex/Main.qml` - patched by `scripts/install.sh`.
- `/usr/share/n4d/python-plugins/AccessControlManager.py` - consulted
  (read-only), never modified.
- `/etc/n4d/conf.d/AccessControlManager.json` - read context only.
- `diagnostico_login_wifigva.sh` on the admin's desktop - the manual script
  this project's logic is ported from.
- `/etc/pam.d/common-auth` - context only; not modified by this project.
