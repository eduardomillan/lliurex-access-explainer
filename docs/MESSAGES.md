# User-facing messages

This is the single source of truth for every sentence `AccessExplainer`
can show a student on the login screen. The English (`en`) column is the
reference text everything else is translated from/checked against; the
running plugin only ever serves `es` or `ca` to the greeter (see
`explainerLang()` in the `Main.qml` patch) - `en` is documentation only,
not a selectable runtime language.

Keep this file in sync with the `MESSAGES` dictionary in
[`n4d-plugin/AccessExplainer.py`](../n4d-plugin/AccessExplainer.py) for
every **implemented** (Phase 1) category — update both in the same
commit. Phase 2 rows are included below with final wording already
agreed, but are **not yet** in the code; see [PHASE2.md](PHASE2.md) and
don't add them to `AccessExplainer.py` until that detection logic is
actually implemented.

Design rules these messages must always follow (see [RISKS.md](RISKS.md)):
- Short: one or two sentences, no technical jargon, no raw log lines, no
  Kerberos/PAM error codes.
- Never confirm or deny whether a given username exists on the system.
- Always end with a next step the student can actually take (try again,
  try another computer, ask a teacher / IT).
- Always available in `es` (Spanish) and `ca` (Valencian); `lang` defaults
  to `es` if the greeter sends anything else.

## Message catalog

| Category key | Phase | Status | Triggered when... | English (`en`) | Spanish (`es`) | Valencian (`ca`) |
|---|---|---|---|---|---|---|
| `local_user_denied` | 1 | Implemented | The username is explicitly locked on **this** machine (`AccessControlManager.get_users_info` → `isLocked`). | Your account is blocked from logging in on this specific computer. Ask a teacher or the school's IT department for help. | Tu cuenta tiene el acceso bloqueado en este ordenador en concreto. Pide ayuda a un profesor o al departamento de informática del centro. | El teu compte té l'accés bloquejat en este ordinador en concret. Demana ajuda a un professor o al departament d'informàtica del centre. |
| `local_group_denied` | 1 | Implemented | One of the user's groups is locked on **this** machine (`AccessControlManager.get_groups_info` → `isLocked`). | One of your groups is blocked from logging in on this computer. Ask a teacher or the school's IT department for help. | Uno de tus grupos tiene el acceso bloqueado en este ordenador. Pide ayuda a un profesor o al departamento de informática del centro. | Un dels teus grups té l'accés bloquejat en este ordinador. Demana ajuda a un professor o al departament d'informàtica del centre. |
| `cdc_denied` | 1 | Implemented | CDC access control is enabled on this machine (`AccessControlManager.get_cdc_info` → `accessControlEnabled`) and the user has none of the allowed groups. | Your account is not authorized to log in on this specific computer. Try another computer in the classroom or ask a teacher. | Tu cuenta no está autorizada a entrar en este ordenador en concreto. Prueba en otro ordenador del aula o avisa a un profesor. | El teu compte no està autoritzat a entrar en este ordinador en concret. Prova en un altre ordinador de l'aula o avisa un professor. |
| `sssd_inactive` | 1 | Implemented | `systemctl is-active sssd` does not report `active` on this machine. | This computer cannot check your account right now because the identity service is not running. Let the school's IT department know. | Este ordenador no puede comprobar tu cuenta ahora mismo porque el servicio de identidad no está en marcha. Avisa al departamento de informática. | Este ordinador no pot comprovar el teu compte ara mateix perquè el servei d'identitat no està en marxa. Avisa el departament d'informàtica. |
| `backend_offline` | 1 | Implemented | The most recent `sssd` backend transition in the journal (within the lookback window) is "offline", not "online". | This computer cannot reach the central server right now. Try again in a few seconds; if it keeps happening, ask a teacher. | Este ordenador no puede comunicarse ahora mismo con el servidor central. Prueba de nuevo en unos segundos; si continúa, avisa a un profesor. | Este ordinador no pot comunicar-se ara mateix amb el servidor central. Torna-ho a provar en uns segons; si continua, avisa un professor. |
| `user_unknown` | 1 | Implemented | A `pam_sss` journal line for this username in the lookback window contains "user unknown". | Your username is not recognized on this computer right now. This may be a temporary connection problem; try again in a few seconds. | No se reconoce tu usuario en este ordenador en este momento. Puede ser un problema temporal de conexión; prueba de nuevo en unos segundos. | No es reconeix el teu usuari en este ordinador en este moment. Pot ser un problema temporal de connexió; torna-ho a provar en uns segons. |
| `auth_failed` | 1 | Implemented | A `pam_sss` journal line for this username in the lookback window contains "authentication failure". | The password is not correct. Check that you typed it correctly (watch out for capital letters and the keyboard language) and try again. | La contraseña no es correcta. Revisa que la has escrito bien (cuidado con mayúsculas y el idioma del teclado) e inténtalo de nuevo. | La contrasenya no és correcta. Revisa que l'has escrita bé (compte amb majúscules i l'idioma del teclat) i torna-ho a provar. |
| `generic` | 1 | Implemented | Fallback: a `pam_sss` line says "permission denied" with no clearer category, or no check above was conclusive, or any internal error occurred. | We couldn't log in with that account. Try again; if the problem continues, ask a teacher or the school's IT department for help. | No se ha podido entrar con esa cuenta. Prueba de nuevo; si el problema continúa, avisa a un profesor o al departamento de informática del centro. | No s'ha pogut entrar amb eixe compte. Torna-ho a provar; si el problema continua, avisa un professor o el departament d'informàtica del centre. |
| `kdc_account_locked` | 2 | Planned, final wording agreed | `KRB5KDC_ERR_CLIENT_REVOKED` found in `sssd_be_EDU.GVA.ES.log` for this user (account locked by the central AD, typically after repeated failed attempts). | Your account has been locked by the central system, probably after several failed attempts. Wait a while and try again, or ask a teacher or the IT department. | Tu cuenta ha sido bloqueada por el sistema central, probablemente tras varios intentos fallidos. Espera un poco e inténtalo de nuevo, o avisa a un profesor o al departamento de informática. | El teu compte ha sigut bloquejat pel sistema central, probablement després de diversos intents fallits. Espera un poc i torna-ho a provar, o avisa un professor o el departament d'informàtica. |
| `kdc_password_expired` | 2 | Planned, final wording agreed | `KRB5KDC_ERR_KEY_EXPIRED` found for this user (the central AD password has expired). | Your password has expired and needs to be renewed. Ask a teacher or the IT department how to reset your GVA ID Digital password. | Tu contraseña ha caducado y necesita renovarse. Pregunta a un profesor o al departamento de informática cómo restablecer la contraseña de tu ID Digital GVA. | La teua contrasenya ha caducat i necessita renovar-se. Pregunta a un professor o al departament d'informàtica com restablir la contrasenya del teu ID Digital GVA. |
| `kdc_policy_restriction` | 2 | Planned, final wording agreed | `KRB5KDC_ERR_POLICY` found for this user (time-of-day / policy restriction set centrally). | Your account can't log in right now due to a time or policy restriction set by the central system. If this keeps happening, ask a teacher or the IT department. | Tu cuenta no puede entrar ahora mismo por una restricción horaria o de política establecida por el sistema central. Si esto persiste, avisa a un profesor o al departamento de informática. | El teu compte no pot entrar ara mateix per una restricció horària o de política establida pel sistema central. Si això persisteix, avisa un professor o el departament d'informàtica. |

## Transient message (shown while waiting for a response)

Shown immediately by `Main.qml` in `onLoginFailed()`, before the N4D call
to `AccessExplainer.explain_login_failure` resolves. Not part of the
`MESSAGES` dictionary (it lives directly in the QML patch, passed through
the theme's own `i18nd()` catalog like every other UI string in
`Main.qml`).

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
