# Known issues

Tracked, open items for this project, each labeled with the same
category GitHub itself uses for issue labels (`bug`, `enhancement`,
`documentation`, `help wanted`, etc.), so this file maps directly to
GitHub Issues whenever this repo's issue tracker is used instead of (or
alongside) this file.

Purely operational/session notes (e.g. "remember to rotate a shared
password", "don't push until told") are **not** listed here - those
live in `AGENTS.md` (local only, not part of the repo) because they
aren't properties of the project itself.

## `bug`

### Font size increase has no visible effect

**Status: unresolved.**

**What was requested**: enlarge every text element in the login box
(username/password fields, login button, pilot-active label) by a
percentage relative to the theme's own default font size - not a
hardcoded absolute size, so it scales correctly regardless of what the
base theme actually uses.

**What was tried**:
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

**Current state**: the background panel color change and the login box
`width`/`height` increase (+20%) both work and are visible on screen.
Only the per-element `font.pixelSize`/`font.pointSize` overrides on
`txtUser`, `txtPass`, `btnLogin`, and the label don't produce any
visible change, on two different real test machines, despite `qmllint`
passing with no warnings.

**Things not yet tried**:
- Confirm the font property binding actually evaluates at all (e.g. a
  temporary `console.log(txtUser.font.pixelSize)` in
  `Component.onCompleted`, inspected via `journalctl -g qml` after a
  real `sddm` restart - the same technique that diagnosed the
  `Qt.locale().name` and `InlineMessage` height bugs).
- Check whether `PlasmaComponents.TextField`/`Button` (Breeze/Plasma
  style) re-apply their own font internally after the control's own
  `font` property is set, overriding it.
- Try setting the whole `font` property to an explicit `Qt.font({...})`
  object instead of just `font.pixelSize`.
- Try scaling via `implicitWidth`/`implicitHeight` instead of `font`.
- Rule out a stale QML disk cache for the `sddm` user.

**Tracked in code**: `sddm-theme-patch/apply_patch.py` -
`ANCHOR_7`/`INSERT_7` (label), `ANCHOR_9`/`INSERT_9` (`txtUser`),
`ANCHOR_10`/`INSERT_10` (`txtPass`), `ANCHOR_11`/`INSERT_11` (`btnLogin`).

### Transient "Checking the reason..." message always shows in English

**Status: unresolved, low impact.** `showWarning(i18nd("lliurex-sddm-theme","Checking the reason for the failure..."))`
goes through the theme's own translation catalog via `i18nd()`, same as
every other stock UI string in `Main.qml`. Since no `es`/`ca@valencia`
`.po`/`.mo` entry exists for this new string (it isn't part of upstream
`lliurex-sddm-theme`), `i18nd()` falls back to echoing the string
unchanged - always English, regardless of the greeter's locale. The
*actual* explanation that replaces it a moment later (from
`AccessExplainer`) is correctly translated, since that one is
pre-translated server-side, not routed through `i18nd()`. Tracked in
[MESSAGES.md](MESSAGES.md) and [PHASE1.md](PHASE1.md). Fix would mean
either adding real translation file entries to a patched
`lliurex-sddm-theme`, or (simpler) just hardcoding the `es`/`ca` text
directly in the QML instead of using `i18nd()` for this one string,
matching how the pilot-active label already does it via `explainerLang()`.

## `enhancement`

### Implement Phase 2 (explicit Kerberos error mapping)

`KRB5KDC_ERR_CLIENT_REVOKED` / `KRB5KDC_ERR_KEY_EXPIRED` / `KRB5KDC_ERR_POLICY`
detection and mapping to the `kdc_account_locked` / `kdc_password_expired`
/ `kdc_policy_restriction` categories. Wording already agreed in
[MESSAGES.md](MESSAGES.md); needs raising `sssd`'s `debug_level` for the
domain section and parsing `/var/log/sssd/sssd_be_EDU.GVA.ES.log`. See
[PHASE2.md](PHASE2.md).

### Finish and validate the `.deb` package

`debian/` scaffolding exists (`control`, `changelog`, `rules`,
`postinst`/`prerm`/`postrm`, `copyright`, `source/format`), reusing
`scripts/install.sh`/`uninstall.sh` directly from the maintainer
scripts rather than duplicating their logic. Not yet built
(`dpkg-buildpackage`) or tested end to end (install, reinstall/upgrade
idempotency, `remove`, `purge`). The `copyright` file currently assumes
GPL-3+ (matching the rest of the LliureX ecosystem) - **not yet
confirmed** as the intended license for this project.

### Pick up the postponed Ansible deployment stage

Deliberately not started yet - see
[FUTURE-ANSIBLE-DEPLOYMENT.md](FUTURE-ANSIBLE-DEPLOYMENT.md). Needed
before moving from today's handful of individual test machines to the
real 4-classroom (~75-machine) pilot. The finished `.deb` package above
would simplify this considerably (an Ansible task becomes "ensure this
package is installed/absent" instead of copying files by hand).

## `help wanted`

### Pedagogical review of the on-screen message wording

All message text ([MESSAGES.md](MESSAGES.md)) was written by this
project's own author/AI assistant aiming for "an average 14-year-old
reading level," but hasn't been reviewed by an actual teacher or
pedagogy-literate staff member. Worth a pass before the real classroom
pilot, in both `es` and `ca`.

## `wontfix`

### Switch `messages.py` to gettext `.po`/`.mo` files

Considered: the rest of the LliureX ecosystem (including
`lliurex-sddm-theme` itself, via `i18nd()`) uses gettext `.po`/`.mo`
catalogs for translations, not plain Python dicts. Decided to keep the
current plain-dict approach in `n4d-plugin/messages.py` instead.

**Why not**: these aren't simple, statically-extractable UI labels -
they're dynamically selected server-side, in Python, based on which
`AccessExplainer` check fires at runtime. Only 3 languages and ~8
message categories exist today, already covered by a test
(`test_messages_cover_en_es_and_ca_for_every_category`). A `.po`/`.mo`
pipeline (`xgettext`/`msgfmt`, runtime `gettext` lookups) would add real
build/runtime complexity for no concrete benefit at this scale.

**When to revisit**: if this project grows real external translators
unfamiliar with the codebase, or becomes a proper distributed
LliureX-ecosystem package expecting community translations (the `.deb`
packaging effort pushes in that direction) - at that point the
consistency and tooling benefits of `.po`/`.mo` would outweigh the
added complexity.
