# Known issues

Open problems that are tracked but not yet resolved. Unlike
[RISKS.md](RISKS.md) (anticipated risks with a mitigation already in
place), this file is for things that are actually broken or not working
as intended right now.

## Font size increase has no visible effect

**Status: unresolved.**

### What was requested

Enlarge every text element in the login box (username/password fields,
login button, pilot-active label) by a percentage relative to the
theme's own default font size - not a hardcoded absolute size, so it
scales correctly regardless of what the base theme actually uses.

### What was tried

1. `font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.1` (then
   `* 1.2`) on `txtUser`, `txtPass`, `btnLogin`, and the pilot-active
   label. **No visible effect at all**, confirmed live on
   `172.28.222.128` after a full install + `sddm` restart.
2. Hypothesis: `Kirigami.Theme.defaultFont.pointSize` returns `-1` when
   the theme's font is actually defined by pixel size (Qt's convention
   for "not set this way", not an error - see [KIRIGAMI.md](KIRIGAMI.md)).
   `-1 * 1.2 = -1.2`, silently treated as "unset" by Qt Quick.
3. Fix attempt: switched to
   `font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2`, which
   should always resolve to a valid positive number regardless of how
   the base font was originally defined. Re-deployed and tested live on
   `172.28.222.128`. **Still no visible effect.**

### Current state

- The background panel color change and the login box `width`/`height`
  increase (+20%, `400x340` -> see `ANCHOR_8` in `apply_patch.py`) both
  work and are visible on screen.
- Only the per-element `font.pixelSize`/`font.pointSize` overrides on
  `txtUser`, `txtPass`, `btnLogin`, and the label don't produce any
  visible change, on two different real test machines.
- `qmllint` passes on the patched file with no warnings for these lines,
  so it isn't a syntax error or an obviously invalid binding.

### Things not yet tried

- Confirm the font property binding actually evaluates at all (e.g. a
  temporary `console.log(txtUser.font.pixelSize)` in
  `Component.onCompleted`, inspected via `journalctl -g qml` after a
  real `sddm` restart - the same technique that diagnosed the
  `Qt.locale().name` and `InlineMessage` height bugs).
- Check whether `PlasmaComponents.TextField`/`Button` (from
  `org.kde.plasma.components 3.0`, Breeze/Plasma style) re-apply their
  own font internally after the control's own `font` property is set,
  overriding it - this would be a style-specific behavior, not a
  Kirigami/Qt Quick Controls standard one.
- Try setting the whole `font` property to an explicit `Qt.font({...})`
  object instead of just `font.pixelSize`, in case partial font-property
  assignment is the issue.
- Try scaling via a completely different mechanism, e.g. wrapping the
  affected controls' `implicitWidth`/`implicitHeight` and letting Qt's
  own DPI/font-scaling settings do the work, instead of touching `font`
  directly on each control.
- Rule out a caching issue: confirm `qmlcachegen`/the QML disk cache
  (`~/.cache/QML/` or similar, if it exists for the `sddm` user running
  the greeter) isn't serving a stale compiled version of `Main.qml`
  despite the file on disk being up to date (`sha256sum` already
  confirmed the file itself is correct both times).

### Where it's tracked in code

`sddm-theme-patch/apply_patch.py` - `ANCHOR_7`/`INSERT_7` (label),
`ANCHOR_9`/`INSERT_9` (`txtUser`), `ANCHOR_10`/`INSERT_10` (`txtPass`),
`ANCHOR_11`/`INSERT_11` (`btnLogin`).
