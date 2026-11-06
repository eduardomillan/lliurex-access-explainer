#!/usr/bin/python3
#
# AccessExplainer - N4D plugin for the lliurex-access-explainer project.
#
# Turns a failed login on a LliureX client into a short, plain-language
# reason that lliurex-sddm-theme (Main.qml) can show instead of the
# generic "Login failed" message. Runs as root (n4d.service is root), so
# it can read everything a human admin could without needing PAM hooks.
#
# Design rules (see docs/ARCHITECTURE.md and docs/RISKS.md for the why):
#   - Only ever call read-only methods on other N4D plugins (get_*/is_*).
#     Never call AccessControlManager.set_cdc_info or
#     disable_access_denied_cdc: those restart sssd as a side effect.
#   - Every check has its own try/except and a short subprocess timeout.
#     One check failing must never prevent the others from running or
#     crash the whole method - the greeter is waiting on this synchronously.
#   - The returned message never includes raw log lines, Kerberos error
#     codes, or anything that confirms/denies whether a given username
#     exists on the system. Only a short, already-translated sentence.

import subprocess

import n4d.responses
import n4d.server.core as n4dcore

SUBPROCESS_TIMEOUT = 3

MESSAGES = {
	"local_user_denied": {
		"es": "Tu cuenta tiene el acceso bloqueado en este ordenador en concreto. Pide ayuda a un profesor o al departamento de informática del centro.",
		"ca": "El teu compte té l'accés bloquejat en este ordinador en concret. Demana ajuda a un professor o al departament d'informàtica del centre.",
	},
	"local_group_denied": {
		"es": "Uno de tus grupos tiene el acceso bloqueado en este ordenador. Pide ayuda a un profesor o al departamento de informática del centro.",
		"ca": "Un dels teus grups té l'accés bloquejat en este ordinador. Demana ajuda a un professor o al departament d'informàtica del centre.",
	},
	"cdc_denied": {
		"es": "Tu cuenta no está autorizada a entrar en este ordenador en concreto. Prueba en otro ordenador del aula o avisa a un profesor.",
		"ca": "El teu compte no està autoritzat a entrar en este ordinador en concret. Prova en un altre ordinador de l'aula o avisa un professor.",
	},
	"sssd_inactive": {
		"es": "Este ordenador no puede comprobar tu cuenta ahora mismo porque el servicio de identidad no está en marcha. Avisa al departamento de informática.",
		"ca": "Este ordinador no pot comprovar el teu compte ara mateix perquè el servei d'identitat no està en marxa. Avisa el departament d'informàtica.",
	},
	"backend_offline": {
		"es": "Este ordenador no puede comunicarse ahora mismo con el servidor central. Prueba de nuevo en unos segundos; si continúa, avisa a un profesor.",
		"ca": "Este ordinador no pot comunicar-se ara mateix amb el servidor central. Torna-ho a provar en uns segons; si continua, avisa un professor.",
	},
	"user_unknown": {
		"es": "No se reconoce tu usuario en este ordenador en este momento. Puede ser un problema temporal de conexión; prueba de nuevo en unos segundos.",
		"ca": "No es reconeix el teu usuari en este ordinador en este moment. Pot ser un problema temporal de connexió; torna-ho a provar en uns segons.",
	},
	"auth_failed": {
		"es": "La contraseña no es correcta. Revisa que la has escrito bien (cuidado con mayúsculas y el idioma del teclado) e inténtalo de nuevo.",
		"ca": "La contrasenya no és correcta. Revisa que l'has escrita bé (compte amb majúscules i l'idioma del teclat) i torna-ho a provar.",
	},
	"generic": {
		"es": "No se ha podido entrar con esa cuenta. Prueba de nuevo; si el problema continúa, avisa a un profesor o al departamento de informática del centro.",
		"ca": "No s'ha pogut entrar amb eixe compte. Torna-ho a provar; si el problema continua, avisa un professor o el departament d'informàtica del centre.",
	},
}


class AccessExplainer:

	def __init__(self):
		self.core = n4dcore.Core.get_core()

	#def __init__

	def ping(self):
		return n4d.responses.build_successful_call_response(True)

	#def ping

	def _msg(self, category, lang):
		lang = "ca" if str(lang).lower().startswith("ca") else "es"
		bucket = MESSAGES.get(category, MESSAGES["generic"])
		return bucket.get(lang, bucket["es"])

	#def _msg

	def _run(self, cmd):
		'''Run a short-lived read-only command, never raise.'''
		try:
			return subprocess.run(
				cmd,
				capture_output=True,
				text=True,
				timeout=SUBPROCESS_TIMEOUT,
			)
		except Exception as e:
			print(f"AccessExplainer._run({cmd}). Error: {e}")
			return None

	#def _run

	def _user_groups(self, username):
		proc = self._run(["id", "-Gn", username])
		if proc is None or proc.returncode != 0 or not proc.stdout:
			return set()
		return {g.lower() for g in proc.stdout.split()}

	#def _user_groups

	def _check_local_deny_lists(self, username, lang):
		'''Fase 1/2: ask AccessControlManager (read-only) whether this user,
		one of their groups, or the CDC allow-list denies login on THIS
		machine. Never calls a write method on that plugin (see module
		docstring).'''
		try:
			acm = self.core.get_plugin("AccessControlManager")
			if acm is None:
				return None
		except Exception as e:
			print(f"AccessExplainer._check_local_deny_lists: AccessControlManager not available. Error: {e}")
			return None

		clean_user = username.lower()

		try:
			users_info = acm.get_users_info().get("return", {}) or {}
			if users_info.get(clean_user, {}).get("isLocked"):
				return self._msg("local_user_denied", lang)
		except Exception as e:
			print(f"AccessExplainer._check_local_deny_lists (users). Error: {e}")

		user_groups = self._user_groups(username)
		if user_groups:
			try:
				groups_info = acm.get_groups_info().get("return", {}) or {}
				for group_name, group_data in groups_info.items():
					if not isinstance(group_data, dict):
						continue
					if group_data.get("isLocked") and group_name.lower() in user_groups:
						return self._msg("local_group_denied", lang)
			except Exception as e:
				print(f"AccessExplainer._check_local_deny_lists (groups). Error: {e}")

		try:
			cdc_info = acm.get_cdc_info().get("return", {}) or {}
			if cdc_info.get("accessControlEnabled") and cdc_info.get("code"):
				allowed = {g.strip().lower() for g in cdc_info["code"].split(",") if g.strip()}
				if allowed and not (user_groups & allowed):
					return self._msg("cdc_denied", lang)
		except Exception as e:
			print(f"AccessExplainer._check_local_deny_lists (cdc). Error: {e}")

		return None

	#def _check_local_deny_lists

	def _check_sssd_service(self, lang):
		proc = self._run(["systemctl", "is-active", "sssd"])
		if proc is not None and proc.stdout.strip() != "active":
			return self._msg("sssd_inactive", lang)
		return None

	#def _check_sssd_service

	def _check_backend_offline(self, minutes, lang):
		proc = self._run(["journalctl", "-u", "sssd", "--since", f"-{minutes}min", "--no-pager"])
		if proc is None or not proc.stdout:
			return None
		lines = [l for l in proc.stdout.splitlines() if "Backend is offline" in l or "Backend is online" in l]
		if lines and "offline" in lines[-1]:
			return self._msg("backend_offline", lang)
		return None

	#def _check_backend_offline

	def _check_pam_log(self, username, minutes, lang):
		proc = self._run(["journalctl", "--since", f"-{minutes}min", "--no-pager", "-g", "pam_sss"])
		if proc is None or not proc.stdout:
			return None
		user_lines = [l for l in proc.stdout.splitlines() if username in l]
		if not user_lines:
			return None
		joined = "\n".join(user_lines).lower()
		if "user unknown" in joined:
			return self._msg("user_unknown", lang)
		if "authentication failure" in joined:
			return self._msg("auth_failed", lang)
		if "permission denied" in joined:
			return self._msg("generic", lang)
		return None

	#def _check_pam_log

	def explain_login_failure(self, username, lang="es", minutes=10):
		'''Anonymous, read-only. Returns an already-translated, short
		sentence explaining a login failure for `username`, or a generic
		fallback sentence if nothing specific was found. Never raises:
		any internal failure degrades to the generic message so the
		greeter always has something safe to show.'''
		try:
			username = str(username or "").strip()
			try:
				minutes = int(minutes)
			except (TypeError, ValueError):
				minutes = 10

			if not username:
				return n4d.responses.build_successful_call_response(self._msg("generic", lang))

			reason = (
				self._check_local_deny_lists(username, lang)
				or self._check_sssd_service(lang)
				or self._check_backend_offline(minutes, lang)
				or self._check_pam_log(username, minutes, lang)
				or self._msg("generic", lang)
			)

			return n4d.responses.build_successful_call_response(reason)

		except Exception as e:
			print(f"AccessExplainer.explain_login_failure. Error: {e}")
			return n4d.responses.build_successful_call_response(self._msg("generic", lang))

	#def explain_login_failure
