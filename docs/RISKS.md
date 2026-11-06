# Risks and mitigations

## 1. `lliurex-sddm-theme` gets updated, overwriting the patch

An `apt upgrade` can replace `Main.qml` with a new pristine version at any
time, silently undoing the Phase 1 patch (or worse, leaving a half-patched
file if the overwrite happens mid-install, though dpkg itself handles that
atomically - the risk is purely "patch silently gone after upgrade").

**Mitigation:**
- `scripts/install.sh` checks the installed `lliurex-sddm-theme` version
  against `sddm-theme-patch/versions.yml` before patching, and refuses to
  patch an unlisted version without `--force`.
- `sddm-theme-patch/Main.qml.patch.txt` keeps a human-readable diff to
  reapply by hand against a new pristine file, then regenerate
  `Main.qml.patched` + checksums and add the new version to
  `versions.yml`.
- `apt-mark hold lliurex-sddm-theme` is a valid option on pilot machines,
  but it's a manual, explicit admin decision - not automated by this
  project.

## 2. N4D packages themselves get updated

Not just the theme: `n4d`, `n4d-lliurex-access-control` (ships
`AccessControlManager.py`), and `qml-module-edupals-n4d` are all regular
apt packages this project integrates with. An update to any of them can
change a method's signature or behavior, or how `Main.qml` talks to N4D,
breaking `AccessExplainer` with no visible error until a student sees a
wrong or missing message.

**Mitigation:**
- Record the exact version of every N4D package used during testing
  (`dpkg-query -W -f='${Version}' <pkg>`), same discipline as for the
  theme.
- `AccessExplainer` must check that the methods it needs on
  `AccessControlManager` actually exist before calling them (defensive
  lookups), and degrade to the generic message if they don't - never
  assume the API is unchanged.
- **Checklist before running `apt upgrade`/`apt dist-upgrade`** on any
  machine with this project installed - review whether these packages are
  in the upgrade set, and re-test Phase 1's end-to-end flow afterwards if
  they are:
  - `lliurex-sddm-theme`
  - `n4d`
  - `n4d-lliurex-access-control`
  - `qml-module-edupals-n4d`

  No automated hold is applied to any of these by default; this is a
  manual checklist, same posture as risk #1.

## 3. `AccessControlManager`'s write methods restart `sssd`

`set_cdc_info()` and `disable_access_denied_cdc(update_cdc_info=True)`
both run `systemctl restart sssd` as a side effect. If `AccessExplainer`
ever called one of those by mistake, every login attempt could trigger an
unwanted `sssd` restart.

**Mitigation:** `AccessExplainer` only calls `get_*`/`is_*` methods on
`AccessControlManager`, enforced as a hard rule in code comments and
verified by a dedicated test
(`test_local_deny_lists_never_raises_on_write_method_only_reads_used` in
`tests/test_access_explainer.py`, which asserts those method names don't
appear in the relevant function's source).

## 4. The plugin breaks the login experience if N4D is unavailable

If N4D is down, `AccessExplainer` isn't installed, or the call times out,
the login screen must never show a broken/empty message or hang.

**Mitigation:** the `onError` handler of the `N4D.Proxy` block in
`Main.qml` always falls back to the theme's original, unmodified
`"Login failed"` string. Inside the plugin itself,
`explain_login_failure()` wraps everything in a single outer
`try`/`except` that also degrades to the generic message - it is designed
to never raise an uncaught exception back to the XML-RPC caller.

## 5. Anonymous exposure of login-failure reasons

`explain_login_failure` is marked `anonymous` in N4D's access control, and
`n4d.service` runs as root - so any local, unprivileged process can ask
for the login-failure reason of **any** username, not just its own.

**Mitigation:** the response is always one of the short, pre-translated
sentences in [MESSAGES.md](MESSAGES.md) - never a raw log line, a
Kerberos/PAM error code, or anything that would let a caller distinguish
"this account doesn't exist" from "this account exists but is locked".

## 6. Latency visible to the student

Every check the plugin runs is a subprocess call (`systemctl`,
`journalctl`, `id`) with its own timeout, and the whole method runs
synchronously while a real student is looking at the login screen -
unlike the manual script, which an admin can run and wait on without
anyone noticing.

**Mitigation:** 2-3 second timeout per subprocess call;
`showWarning("Checking the reason for the failure...")` is shown
immediately so the screen isn't blank while waiting; `onError` degrades
instantly if the N4D call itself fails or times out.

## 7. Accidental login breakage while testing on this ThinkPad

Patching `Main.qml` on the only machine in use for development risks
losing the ability to log in at all if something goes wrong.

**Mitigation:** see [TESTING.md](TESTING.md) - `sddm` is never restarted
automatically by `install.sh`/`uninstall.sh`; `sddm-greeter --test-mode`
is used to visually validate the new greeter without touching the active
session; a second virtual terminal with a root shell and the rollback
command ready is kept open before ever restarting `sddm` for real.
