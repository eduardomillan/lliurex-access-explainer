# lliurex-access-explainer

Turns a failed login on a LliureX school client into a short,
plain-language reason shown directly on the login screen - instead of the
generic "Login failed" - for students logging in with their GVA
Microsoft/ID Digital account against the `EDU.GVA.ES` Active Directory
domain via SSSD.

## Why

Sometimes a student's account authenticates correctly against Active
Directory but the login is still rejected, with zero indication of why -
neither to the student nor to whoever is helping them in the classroom. A
manual diagnostic script already existed for an admin to run *after* the
fact (see [`diagnose/`](diagnose/)); this project surfaces that same kind
of explanation *at the moment of failure*, on screen.

## How

A small N4D plugin (`AccessExplainer`) reuses checks already available on
any LliureX client (SSSD/journal status, the existing
`AccessControlManager` local access lists) to produce a short sentence in
Spanish or Valencian, and a minimal patch to the LliureX SDDM theme
(`Main.qml`) asks that plugin for a reason right when a login fails and
shows it - reusing a pattern the theme already uses for its WiFi
integration. No PAM changes. Full design rationale in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Status

Early development, tested only on a single ThinkPad. **Not deployed
anywhere else.** No Ansible/automation yet - see
[`docs/FUTURE-ANSIBLE-DEPLOYMENT.md`](docs/FUTURE-ANSIBLE-DEPLOYMENT.md)
for why that's deliberately postponed.

## Layout

| Path | What |
|---|---|
| [`n4d-plugin/`](n4d-plugin/) | The `AccessExplainer` N4D plugin and its config |
| [`sddm-theme-patch/`](sddm-theme-patch/) | The `Main.qml` patch, its generator script, and supported-version tracking |
| [`scripts/`](scripts/) | Manual `install.sh` / `uninstall.sh` for this ThinkPad |
| [`tests/`](tests/) | Unit tests for the plugin (no root, no real N4D needed) |
| [`diagnose/`](diagnose/) | The original manual, post-incident diagnostic script this project's logic is ported from |
| [`docs/`](docs/) | Architecture, phase breakdown, message catalog, risks, testing guide |

## Getting started

```bash
python3 -m pytest tests/ -q      # unit tests, safe anywhere
sudo ./scripts/install.sh --plugin-only   # plugin only, no theme patch yet
```

See [`docs/TESTING.md`](docs/TESTING.md) for the full, safe test sequence
before ever restarting `sddm` for real.

## Documentation index

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - how this works and why
- [`docs/PHASE1.md`](docs/PHASE1.md) - plain-language message on login failure (implemented)
- [`docs/PHASE2.md`](docs/PHASE2.md) - finer-grained causes (not implemented yet)
- [`docs/MESSAGES.md`](docs/MESSAGES.md) - the full catalog of on-screen messages
- [`docs/RISKS.md`](docs/RISKS.md) - risks and mitigations
- [`docs/TESTING.md`](docs/TESTING.md) - how to test safely on this machine
- [`docs/FUTURE-ANSIBLE-DEPLOYMENT.md`](docs/FUTURE-ANSIBLE-DEPLOYMENT.md) - postponed deployment plan sketch
- [`docs/KIRIGAMI.md`](docs/KIRIGAMI.md) - notes on the QML framework behind the login screen, and two real bugs it caused here
