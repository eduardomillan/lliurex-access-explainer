# Checking an `lliurex-sddm-theme` pristine sha256 mismatch

Covers the case where `scripts/install.sh` refuses to patch a machine
with:

```
ERROR: installed Main.qml does not match the known pristine sha256 for this version
```

This is the mitigation for [Risk #1](RISKS.md#1-lliurex-sddm-theme-gets-updated-overwriting-the-patch)
in `docs/RISKS.md`: the installed `lliurex-sddm-theme` version string
matches an entry in `sddm-theme-patch/versions.yml`, but the actual
content of the installed `Main.qml` does not match either the
`sha256_pristine` or `sha256_patched` recorded for that version.

## Commands to run on the affected machine

```
dpkg-query -W -f='${Version}\n' lliurex-sddm-theme
sha256sum /usr/share/sddm/themes/lliurex/Main.qml
```

Compare the resulting sha256 against the `sha256_pristine` /
`sha256_patched` values recorded for that `theme_version` in
`sddm-theme-patch/versions.yml`.

- Matches `sha256_patched` -> the file is already patched;
  `install.sh` should report that and do nothing, not error out.
- Matches `sha256_pristine` -> expected, clean state; `install.sh`
  should proceed to patch normally.
- Matches neither -> the mismatch this document is about.

## Likely causes when the version string matches but the sha256 matches neither

1. The file is already patched from an earlier session, but with a
   `Main.qml.patched` from a different, uncommitted version of the
   patch than the one currently in `sddm-theme-patch/` - so it matches
   neither the current pristine nor the current patched sha256.
2. A previous patch attempt was interrupted or left the file in an
   intermediate/corrupted state (e.g. a failed `apply_patch.py` run,
   or a backup restored incorrectly).
3. The package content actually changed without the version string
   changing - unusual for `dpkg`, but possible if the machine pulled
   from a different repo/mirror, or the package was reinstalled from a
   rebuilt `.deb` with the same version number.

Case 1 is the most common in this project, since several test
machines have had patches applied and rolled back repeatedly during
development (see `docs/TESTING.md`).

## How to resolve

1. Confirm which of the three cases above applies by diffing the
   installed `Main.qml` against both `sddm-theme-patch/Main.qml.pristine`
   and `sddm-theme-patch/Main.qml.patched` from the repo (not just
   comparing shas) - this shows what actually differs.
2. If it's an old/different patched version (case 1): restore the
   backup made by `install.sh` (or reinstall the `lliurex-sddm-theme`
   package to get a clean pristine file), then re-run `install.sh`.
3. If the package itself changed (case 3): capture the new pristine
   file and regenerate the patch, following the header comment in
   `sddm-theme-patch/versions.yml` (`cp` the new pristine, run
   `apply_patch.py`, regenerate the diff, add the new version entry).
4. Never use `--force` on `install.sh` to paper over a sha mismatch
   without first understanding which case it is - patching over an
   unknown file state can leave the greeter broken with no visible
   error until a student hits it.

## 2026-11-17 status note

Checked on the ThinkPad (`prn5-10366948`): installed `lliurex-sddm-theme`
is `23.8.0.0` and the live `Main.qml` sha256 matches `sha256_pristine`
in `versions.yml` exactly - no mismatch there.

The mismatch was reported on `172.28.222.128` (`bocairent`). Not yet
checked remotely as of this note - re-run the commands above there and
update this section once confirmed.
