# User-facing messages

This is the single source of truth for every sentence `AccessExplainer` can
show a student on the login screen. Keep it in sync with the `MESSAGES`
dictionary in [`n4d-plugin/AccessExplainer.py`](../n4d-plugin/AccessExplainer.py)
— whenever that dictionary changes, update this table in the same commit.

Design rules these messages must always follow (see [RISKS.md](RISKS.md)):
- Short: one or two sentences, no technical jargon, no raw log lines, no
  Kerberos/PAM error codes.
- Never confirm or deny whether a given username exists on the system.
- Always end with a next step the student can actually take (try again,
  try another computer, ask a teacher / IT).
- Always available in `es` (Spanish) and `ca` (Valencian); `lang` defaults
  to `es` if the greeter sends anything else.

## Message catalog

| Category key         | Triggered when...                                                                                   | Spanish (`es`)                                                                                                                              | Valencian (`ca`)                                                                                                                                 |
|-----------------------|-------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| `local_user_denied`   | The username is explicitly locked on **this** machine (`AccessControlManager.get_users_info` → `isLocked`). | Tu cuenta tiene el acceso bloqueado en este ordenador en concreto. Pide ayuda a un profesor o al departamento de informática del centro.     | El teu compte té l'accés bloquejat en este ordinador en concret. Demana ajuda a un professor o al departament d'informàtica del centre.          |
| `local_group_denied`  | One of the user's groups is locked on **this** machine (`AccessControlManager.get_groups_info` → `isLocked`). | Uno de tus grupos tiene el acceso bloqueado en este ordenador. Pide ayuda a un profesor o al departamento de informática del centro.         | Un dels teus grups té l'accés bloquejat en este ordinador. Demana ajuda a un professor o al departament d'informàtica del centre.                 |
| `cdc_denied`          | CDC access control is enabled on this machine (`AccessControlManager.get_cdc_info` → `accessControlEnabled`) and the user has none of the allowed groups. | Tu cuenta no está autorizada a entrar en este ordenador en concreto. Prueba en otro ordenador del aula o avisa a un profesor.                 | El teu compte no està autoritzat a entrar en este ordinador en concret. Prova en un altre ordinador de l'aula o avisa un professor.               |
| `sssd_inactive`       | `systemctl is-active sssd` does not report `active` on this machine.                                  | Este ordenador no puede comprobar tu cuenta ahora mismo porque el servicio de identidad no está en marcha. Avisa al departamento de informática. | Este ordinador no pot comprovar el teu compte ara mateix perquè el servei d'identitat no està en marxa. Avisa el departament d'informàtica.       |
| `backend_offline`     | The most recent `sssd` backend transition in the journal (within the lookback window) is "offline", not "online". | Este ordenador no puede comunicarse ahora mismo con el servidor central. Prueba de nuevo en unos segundos; si continúa, avisa a un profesor.  | Este ordinador no pot comunicar-se ara mateix amb el servidor central. Torna-ho a provar en uns segons; si continua, avisa un professor.          |
| `user_unknown`        | A `pam_sss` journal line for this username in the lookback window contains "user unknown".            | No se reconoce tu usuario en este ordenador en este momento. Puede ser un problema temporal de conexión; prueba de nuevo en unos segundos.    | No es reconeix el teu usuari en este ordinador en este moment. Pot ser un problema temporal de connexió; torna-ho a provar en uns segons.         |
| `auth_failed`         | A `pam_sss` journal line for this username in the lookback window contains "authentication failure".  | La contraseña no es correcta. Revisa que la has escrito bien (cuidado con mayúsculas y el idioma del teclado) e inténtalo de nuevo.           | La contrasenya no és correcta. Revisa que l'has escrita bé (compte amb majúscules i l'idioma del teclat) i torna-ho a provar.                     |
| `generic`             | Fallback: a `pam_sss` line says "permission denied" with no clearer category, or no check above was conclusive, or any internal error occurred. | No se ha podido entrar con esa cuenta. Prueba de nuevo; si el problema continúa, avisa a un profesor o al departamento de informática del centro. | No s'ha pogut entrar amb eixe compte. Torna-ho a provar; si el problema continua, avisa un professor o el departament d'informàtica del centre. |

## Transient message (shown while waiting for a response)

Shown immediately by `Main.qml` in `onLoginFailed()`, before the N4D call
to `AccessExplainer.explain_login_failure` resolves. Not part of the
`MESSAGES` dictionary (it lives directly in the QML patch).

| Spanish                                   | Valencian                                     |
|--------------------------------------------|-------------------------------------------------|
| Comprobando el motivo del fallo...         | Comprovant el motiu de la fallada...            |

> Note: the QML patch currently ships the English string
> `"Checking the reason for the failure..."` translated through the theme's
> own `i18nd()` catalog, same as every other string in `Main.qml`
> (`"Login failed"`, `"GVA Wifi"`, etc.) — the `.po`/`.mo` translation for
> `es`/`ca@valencia` must be added to `lliurex-sddm-theme`'s own translation
> files for it to render translated; until then it will show in English
> as a fallback. Track this in [PHASE1.md](PHASE1.md).

## Fallback when `AccessExplainer` cannot be reached at all

If N4D is down, the plugin is not installed, or the call times out, the
`onError` handler in `Main.qml` shows the theme's original, unmodified
string — never a broken or empty message:

| String shown                 |
|-------------------------------|
| `Login failed` (theme default, via `i18nd`) |

## Planned additions (Phase 2 — not implemented yet)

These categories are designed in [PHASE2.md](PHASE2.md) but not yet coded
in `AccessExplainer.py`. Listed here so this table stays the complete,
up-to-date catalog once they land — update the rows above (don't just
append) when they're implemented.

| Category key (planned)     | Triggered when...                                                        |
|------------------------------|----------------------------------------------------------------------------|
| `kdc_account_locked`         | `KRB5KDC_ERR_CLIENT_REVOKED` found in `sssd_be_EDU.GVA.ES.log` for this user. |
| `kdc_password_expired`       | `KRB5KDC_ERR_KEY_EXPIRED` found for this user.                            |
| `kdc_policy_restriction`     | `KRB5KDC_ERR_POLICY` found for this user (time-of-day / policy restriction). |
