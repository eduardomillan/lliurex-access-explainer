#!/usr/bin/python3
#
# messages.py - the on-screen text catalog for AccessExplainer.
#
# Kept in its own file (not inline in AccessExplainer.py) so the wording
# can be reviewed/edited on its own. Must stay in sync with
# docs/MESSAGES.md - update both in the same commit.
#
# Wording rules (see docs/MESSAGES.md and docs/RISKS.md for the why):
#   - Short sentences, everyday words, aimed at an average 14-year-old
#     student - not an IT admin. No jargon ("identity service", "access
#     filter", "policy restriction"...). Say what happened and what to
#     do next, nothing else.
#   - Never confirm or deny whether a given username exists on the system.
#   - "en" is the reference translation everything else is checked
#     against; the running plugin only ever gets asked for "es" or "ca"
#     by the greeter (see explainerLang() in the Main.qml patch), but all
#     three are real, selectable languages here, not documentation-only.
#
# Only the categories AccessExplainer.py's checks can actually produce go
# here. Phase 2 categories (see docs/PHASE2.md) are designed and already
# worded in docs/MESSAGES.md, but don't add them here until the matching
# detection logic is implemented.

MESSAGES = {
	"local_user_denied": {
		"en": "You can't log in with your account on this computer. Ask a teacher or IT for help.",
		"es": "No puedes entrar con tu cuenta en este ordenador. Pide ayuda a un profesor o a informática.",
		"ca": "No pots entrar amb el teu compte en este ordinador. Demana ajuda a un professor o a informàtica.",
	},
	"local_group_denied": {
		"en": "You can't log in with your account on this computer. Ask a teacher or IT for help.",
		"es": "No puedes entrar con tu cuenta en este ordenador. Pide ayuda a un profesor o a informática.",
		"ca": "No pots entrar amb el teu compte en este ordinador. Demana ajuda a un professor o a informàtica.",
	},
	"cdc_denied": {
		"en": "Your account can't log in on this computer. Try another computer in the classroom or ask a teacher.",
		"es": "Tu cuenta no puede entrar en este ordenador. Prueba otro ordenador del aula o avisa a un profesor.",
		"ca": "El teu compte no pot entrar en este ordinador. Prova un altre ordinador de l'aula o avisa un professor.",
	},
	"sssd_inactive": {
		"en": "This computer can't check your account right now. Ask a teacher or IT.",
		"es": "Este ordenador no puede comprobar tu cuenta ahora mismo. Avisa a un profesor o a informática.",
		"ca": "Este ordinador no pot comprovar el teu compte ara mateix. Avisa un professor o informàtica.",
	},
	"backend_offline": {
		"en": "This computer can't connect right now. Wait a few seconds and try again; if it keeps happening, ask a teacher.",
		"es": "Este ordenador no se puede conectar ahora mismo. Espera unos segundos y prueba otra vez; si sigue igual, avisa a un profesor.",
		"ca": "Este ordinador no es pot connectar ara mateix. Espera uns segons i torna-ho a provar; si continua igual, avisa un professor.",
	},
	"user_unknown": {
		"en": "This computer doesn't recognize your username right now. It might be a connection problem; wait a few seconds and try again.",
		"es": "Este ordenador no reconoce tu usuario ahora mismo. Puede ser un problema de conexión; espera unos segundos y prueba otra vez.",
		"ca": "Este ordinador no reconeix el teu usuari ara mateix. Pot ser un problema de connexió; espera uns segons i torna-ho a provar.",
	},
	"auth_failed": {
		"en": "The password isn't correct. Check that you typed it right (capital letters, keyboard language) and try again.",
		"es": "La contraseña no es correcta. Revisa que la escribes bien (mayúsculas e idioma del teclado) y prueba otra vez.",
		"ca": "La contrasenya no és correcta. Revisa que l'escrius bé (majúscules i idioma del teclat) i torna-ho a provar.",
	},
	"local_account": {
		"en": "That username is a local account on this computer, not a student account. Check you typed your own username correctly.",
		"es": "Ese usuario es una cuenta local de este ordenador, no una cuenta de alumno. Revisa que has escrito bien tu usuario.",
		"ca": "Eixe usuari és un compte local d'este ordinador, no un compte d'alumne. Revisa que has escrit bé el teu usuari.",
	},
	"generic": {
		"en": "We couldn't log in with that account. Try again; if it keeps failing, ask a teacher or IT.",
		"es": "No se ha podido entrar con esa cuenta. Prueba otra vez; si sigue sin funcionar, avisa a un profesor o a informática.",
		"ca": "No s'ha pogut entrar amb eixe compte. Torna-ho a provar; si continua sense funcionar, avisa un professor o informàtica.",
	},
}
