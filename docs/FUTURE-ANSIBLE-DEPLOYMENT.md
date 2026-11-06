# Future deployment stage: Ansible (postponed - sketch only)

**Status: not started. No roles, inventories, or playbooks exist yet.**
This document only records the intent discussed while designing this
project, so that context isn't lost - it is explicitly **not** a
commitment to build this now, and it is **not** one of the two feature
phases (see [ARCHITECTURE.md](ARCHITECTURE.md) for why those are kept
separate from this).

## When to pick this up

Only after the full install → verify → uninstall → verify-clean cycle in
[TESTING.md](TESTING.md) has been run successfully, more than once, by
hand, on the ThinkPad test machine.

## Sketch of the intended shape

- `scripts/install.sh` / `scripts/uninstall.sh` get reimplemented as
  Ansible roles, driven by a single state variable instead of duplicated
  install/uninstall playbooks:

  ```yaml
  # roles/*/tasks/main.yml
  - include_tasks: install.yml
    when: access_explainer_state | default('present') == 'present'
  - include_tasks: uninstall.yml
    when: access_explainer_state | default('present') == 'absent'
  ```

- Likely roles: `lliurex_access_explainer_n4d` (the plugin) and
  `lliurex_sddm_theme_patch` (the `Main.qml` patch) - kept separate so
  either can be installed/uninstalled independently, same as
  `scripts/install.sh --plugin-only` does today.
- Tags: `phase1`, `phase2`, `n4d_plugin`, `sddm_patch`.
- Inventories: only `thinkpad` and, later, `pilot-4-classrooms` (the
  ~75-machine pilot). **No "whole fleet" inventory ever goes into this
  repo** - a run without an explicit `-i` should fail rather than touch
  anything unintended.
- No automatic `sddm` restart in any role, same rule as the current
  scripts - that always stays an explicit, separate step.

## Open questions for when this actually starts

- Whether to reuse `sddm-theme-patch/versions.yml`'s version/sha256
  checks as Ansible `assert` tasks, or reimplement them in Python via a
  module/script task.
- Whether classroom machines need a different `AccessExplainer.json`
  (e.g. different `allowed_groups`) than this ThinkPad.
- How to handle the one-time backup directory
  (`/var/backups/lliurex-access-explainer/`) idempotently across
  ~75 machines without clobbering any machine-specific state.
