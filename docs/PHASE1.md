# Phase 1 - plain-language message on login failure

## Goal

Replace the generic "Login failed" message with a short, plain-language
explanation, reusing the existing N4D + SDDM theme integration (see
[ARCHITECTURE.md](ARCHITECTURE.md)).

## What's implemented

### `AccessExplainer` N4D plugin

- `n4d-plugin/AccessExplainer.py` + `n4d-plugin/AccessExplainer.json`.
- One anonymous, read-only method: `explain_login_failure(username, lang="es", minutes=10)`.
- Checks, in priority order (first non-`None` result wins - see
  [MESSAGES.md](MESSAGES.md) for the exact sentences):
  1. Local deny-lists via `AccessControlManager` (read-only methods only -
     user, group, and CDC allow-list checks).
  2. `sssd` service active/inactive.
  3. Most recent `Backend is (offline|online)` transition for `sssd` in
     the journal, within the `minutes` lookback window.
  4. `pam_sss` journal lines mentioning this username within the lookback
     window, classified into "user unknown" / "authentication failure" /
     generic "permission denied".
  5. Generic fallback sentence.
- Every step has its own `try`/`except` and a 2-3 second subprocess
  timeout; one step failing never stops the others or crashes the whole
  call - the greeter is waiting on this synchronously, so the whole method
  must stay fast and never raise.

### `Main.qml` patch

- `sddm-theme-patch/Main.qml.pristine` - exact copy of the file as shipped
  by `lliurex-sddm-theme` 23.8.0.0 on this ThinkPad.
- `sddm-theme-patch/apply_patch.py` - regenerates `Main.qml.patched` from
  the pristine copy by applying three additive, anchor-matched changes
  (fails loudly instead of silently mis-patching if the anchors don't
  match exactly once):
  1. Adds an `explainerLang()` helper next to `showWarning()`.
  2. Adds a new `N4D.Proxy { id: local_explain_login_failure; plugin: "AccessExplainer"; method: "explain_login_failure" }`
     block, right next to the existing `WifiEduGva` proxies.
  3. Rewrites `onLoginFailed()` to show a transient "checking the
     reason..." message and call `local_explain_login_failure.call([txtUser.text, explainerLang()])`;
     `onError` on that proxy falls back to the original "Login failed"
     string, so a missing/broken plugin degrades to exactly today's
     behavior, never to something worse.
- `sddm-theme-patch/Main.qml.patch.txt` - the resulting diff, kept for
  reference and for manually reapplying the same three changes to a future
  theme version.
- `sddm-theme-patch/versions.yml` - records which `lliurex-sddm-theme`
  version(s) this patch is known to apply cleanly to, with the sha256 of
  both the pristine and the patched file.

### Known translation gap

The transient message `"Checking the reason for the failure..."` and the
real explanation string are passed through `showWarning()`/`showError()`
as plain QML strings. The transient one goes through the theme's own
`i18nd()` catalog like every other UI string in `Main.qml` - until a
`es`/`ca@valencia` translation is added to `lliurex-sddm-theme`'s own
`.po`/`.mo` files, it will render in English. The actual explanation
string returned by `AccessExplainer` is already pre-translated server-side
(the plugin picks `es` or `ca` itself based on the `lang` argument), so
that one is correct from day one. Tracked here, not yet fixed.

## Not needed for Phase 1

- No PAM changes.
- No changes to `AccessControlManager` or any other existing N4D plugin -
  `AccessExplainer` only calls their already-public read methods.
- No `sddm` restart automation - `scripts/install.sh` never restarts
  `sddm` itself; that's a manual, deliberate step (see
  [TESTING.md](TESTING.md)).
