# User-facing messages

This is the single source of truth for every sentence `AccessExplainer`
can show a student on the login screen. All three languages are real,
selectable text (not just documentation) in
[`n4d-plugin/messages.py`](../n4d-plugin/messages.py) - a separate file
from `AccessExplainer.py` on purpose, so wording can be reviewed/edited
on its own. The running plugin only ever gets asked for `es` or `ca` by
the greeter (see `explainerLang()` in the `Main.qml` patch); `en` is kept
as the reference translation everything else is checked against.

Keep this file in sync with `n4d-plugin/messages.py` for every
**implemented** (Phase 1) category — update both in the same commit.
Phase 2 rows are included below with final wording already agreed, but
are **not yet** in the code; see [PHASE2.md](PHASE2.md) and don't add
them to `messages.py` until that detection logic is actually implemented.

Design rules these messages must always follow (see [RISKS.md](RISKS.md)):
- Written for an average 14-year-old student, not an IT admin: short
  sentences, everyday words, no jargon ("identity service", "access
  filter", "policy restriction"...).
- Never confirm or deny whether a given username exists on the system.
- Always end with a next step the student can actually take (try again,
  try another computer, ask a teacher / IT).
- Always available in `en`, `es` (Spanish) and `ca` (Valencian); `lang`
  defaults to `es` if the greeter sends anything else.

On screen, each message is shown with its category key appended in
brackets, e.g. `... [generic]` - a pilot/debug aid requested while
testing, so testers can tell which branch fired without checking logs.
See `AccessExplainer._format()`.

## Message catalog

| Category key | Phase | Status | Triggered when... | English (`en`) | Spanish (`es`) | Valencian (`ca`) |
|---|---|---|---|---|---|---|
| `local_user_denied` | 1 | Implemented | The username is explicitly locked on **this** machine (`AccessControlManager.get_users_info` → `isLocked`). | You can't log in with your account on this computer. Ask a teacher or IT for help. | No puedes entrar con tu cuenta en este ordenador. Pide ayuda a un profesor o a informática. | No pots entrar amb el teu compte en este ordinador. Demana ajuda a un professor o a informàtica. |
| `local_group_denied` | 1 | Implemented | One of the user's groups is locked on **this** machine (`AccessControlManager.get_groups_info` → `isLocked`). Same wording as `local_user_denied` - the distinction isn't actionable by a student either way, only the `[category]` debug tag tells them apart. | You can't log in with your account on this computer. Ask a teacher or IT for help. | No puedes entrar con tu cuenta en este ordenador. Pide ayuda a un profesor o a informática. | No pots entrar amb el teu compte en este ordinador. Demana ajuda a un professor o a informàtica. |
| `cdc_denied` | 1 | Implemented | CDC access control is enabled on this machine (`AccessControlManager.get_cdc_info` → `accessControlEnabled`) and the user has none of the allowed groups. | Your account can't log in on this computer. Try another computer in the classroom or ask a teacher. | Tu cuenta no puede entrar en este ordenador. Prueba otro ordenador del aula o avisa a un profesor. | El teu compte no pot entrar en este ordinador. Prova un altre ordinador de l'aula o avisa un professor. |
| `sssd_inactive` | 1 | Implemented | `systemctl is-active sssd` does not report `active` on this machine. | This computer can't check your account right now. Ask a teacher or IT. | Este ordenador no puede comprobar tu cuenta ahora mismo. Avisa a un profesor o a informática. | Este ordinador no pot comprovar el teu compte ara mateix. Avisa un professor o informàtica. |
| `backend_offline` | 1 | Implemented | The most recent `sssd` backend transition in the journal (within the lookback window) is "offline", not "online". | This computer can't connect right now. Wait a few seconds and try again; if it keeps happening, ask a teacher. | Este ordenador no se puede conectar ahora mismo. Espera unos segundos y prueba otra vez; si sigue igual, avisa a un profesor. | Este ordinador no es pot connectar ara mateix. Espera uns segons i torna-ho a provar; si continua igual, avisa un professor. |
| `user_unknown` | 1 | Implemented | A `pam_sss` journal line for this username in the lookback window contains "user unknown". | This computer doesn't recognize your username right now. It might be a connection problem; wait a few seconds and try again. | Este ordenador no reconoce tu usuario ahora mismo. Puede ser un problema de conexión; espera unos segundos y prueba otra vez. | Este ordinador no reconeix el teu usuari ara mateix. Pot ser un problema de connexió; espera uns segons i torna-ho a provar. |
| `auth_failed` | 1 | Implemented | A `pam_sss` journal line for this username in the lookback window contains "authentication failure". | The password isn't correct. Check that you typed it right (capital letters, keyboard language) and try again. | La contraseña no es correcta. Revisa que la escribes bien (mayúsculas e idioma del teclado) y prueba otra vez. | La contrasenya no és correcta. Revisa que l'escrius bé (majúscules i idioma del teclat) i torna-ho a provar. |
| `generic` | 1 | Implemented | Fallback: a `pam_sss` line says "permission denied" with no clearer category, or no check above was conclusive, or any internal error occurred. | We couldn't log in with that account. Try again; if it keeps failing, ask a teacher or IT. | No se ha podido entrar con esa cuenta. Prueba otra vez; si sigue sin funcionar, avisa a un profesor o a informática. | No s'ha pogut entrar amb eixe compte. Torna-ho a provar; si continua sense funcionar, avisa un professor o informàtica. |
| `kdc_account_locked` | 2 | Planned, final wording agreed | `KRB5KDC_ERR_CLIENT_REVOKED` found in `sssd_be_EDU.GVA.ES.log` for this user (account locked by the central AD, typically after repeated failed attempts). | Your account got locked, probably after several failed attempts. Wait a bit and try again, or ask a teacher or IT. | Tu cuenta se ha bloqueado, seguramente por varios intentos fallidos. Espera un poco y prueba otra vez, o avisa a un profesor o a informática. | El teu compte s'ha bloquejat, segurament per diversos intents fallits. Espera un poc i torna-ho a provar, o avisa un professor o informàtica. |
| `kdc_password_expired` | 2 | Planned, final wording agreed | `KRB5KDC_ERR_KEY_EXPIRED` found for this user (the central AD password has expired). | Your password expired. Ask a teacher or IT how to reset it. | Tu contraseña ha caducado. Pregunta a un profesor o a informática cómo cambiarla. | La teua contrasenya ha caducat. Pregunta a un professor o a informàtica com canviar-la. |
| `kdc_policy_restriction` | 2 | Planned, final wording agreed | `KRB5KDC_ERR_POLICY` found for this user (time-of-day / policy restriction set centrally). | You can't log in right now because of a schedule or system rule. If it keeps happening, ask a teacher or IT. | Ahora mismo no puedes entrar con tu cuenta por un horario o una restricción del sistema. Si sigue pasando, avisa a un profesor o a informática. | Ara mateix no pots entrar amb el teu compte per un horari o una restricció del sistema. Si continua passant, avisa un professor o informàtica. |

## Transient message (shown while waiting for a response)

Shown immediately by `Main.qml` in `onLoginFailed()`, before the N4D call
to `AccessExplainer.explain_login_failure` resolves. Not part of
`messages.py` (it lives directly in the QML patch, passed through the
theme's own `i18nd()` catalog like every other UI string in `Main.qml`).

| English (`en`) | Spanish (`es`) | Valencian (`ca`) |
|---|---|---|
| Checking the reason for the failure... | Comprobando el motivo del fallo... | Comprovant el motiu de la fallada... |

> Note: until a `es`/`ca@valencia` translation for this exact string is
> added to `lliurex-sddm-theme`'s own `.po`/`.mo` translation files, it
> will render in English (the `i18nd()` fallback) regardless of the
> greeter's locale. Tracked in [PHASE1.md](PHASE1.md). The `es`/`ca`
> columns above are the target translations to add there, not something
> this project's own files currently serve.

## Fallback when `AccessExplainer` cannot be reached at all

If N4D is down, the plugin is not installed, or the call times out, the
`onError` handler in `Main.qml` shows the theme's own original string -
never a broken or empty message:

| String shown |
|---|
| `Login failed` (theme default, via `i18nd`) |
