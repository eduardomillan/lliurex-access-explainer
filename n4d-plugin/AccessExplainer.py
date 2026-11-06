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

import concurrent.futures
import importlib.util
import os
import re
import subprocess

import n4d.responses
import n4d.server.core as n4dcore

# n4d loads each plugin by explicit file path (SourceFileLoader), not via
# a regular package import, so there's no guarantee /usr/share/n4d/
# python-plugins is on sys.path for a plain "import messages" to find its
# sibling file - it might work by accident, or fail only in production
# and not in tests (where the test file inserts this directory into
# sys.path itself). Load it by path explicitly instead, so it works the
# same way in both contexts.
_here = os.path.dirname(os.path.abspath(__file__))
_messages_spec = importlib.util.spec_from_file_location(
	"access_explainer_messages", os.path.join(_here, "messages.py")
)
_messages_module = importlib.util.module_from_spec(_messages_spec)
_messages_spec.loader.exec_module(_messages_module)
MESSAGES = _messages_module.MESSAGES

SUBPROCESS_TIMEOUT = 2
# Upper bound for the three subprocess-backed checks combined, run in
# parallel below. Found in the field: running them sequentially let two
# SUBPROCESS_TIMEOUT journalctl calls add up (3s + 3s) and exceed the N4D
# client's own read timeout, right after a system update made journalctl
# itself slower than usual. A single bounded wait caps the worst case to
# roughly one SUBPROCESS_TIMEOUT instead of their sum.
PARALLEL_CHECKS_TIMEOUT = SUBPROCESS_TIMEOUT + 1

# pam_sss logs a numeric code on its own "received for user X: <code>
# (<description>)" line. The code is locale-independent; the
# parenthesised description is not ("Usuari desconegut...", "User not
# known...", etc. depending on system language) and never reliably
# contains one fixed substring to match on - confirmed in the field: a
# bare "authentication failure" line is present for EVERY failed
# attempt regardless of cause, so matching on description text alone
# always fell through to "auth_failed" even for a nonexistent username.
# Matching the numeric code instead distinguishes them correctly.
#   10 = user unknown to this authentication module (nonexistent
#        account, or a local-only account pam_sss doesn't know about)
#    7 = generic authentication error (wrong password for a real account)
PAM_SSS_CODE_CATEGORY = {
	10: "user_unknown",
	7: "auth_failed",
}
PAM_SSS_RECEIVED_RE = re.compile(r"received for user [^:]+:\s*(\d+)")



class AccessExplainer:

	def __init__(self):
		self.core = n4dcore.Core.get_core()

	#def __init__

	def ping(self):
		return n4d.responses.build_successful_call_response(True)

	#def ping

	def _msg(self, category, lang):
		lang = str(lang).lower()
		if lang.startswith("ca"):
			lang = "ca"
		elif lang.startswith("en"):
			lang = "en"
		else:
			lang = "es"
		bucket = MESSAGES.get(category, MESSAGES["generic"])
		return bucket.get(lang, bucket["es"])

	#def _msg

	def _tag(self, category, lang):
		'''Like _msg, but also carries the category key along with the
		text, as a (category, text) tuple - every check function below
		returns this instead of a plain string so the pilot/debug key
		can be appended to the final message in explain_login_failure.'''
		return (category, self._msg(category, lang))

	#def _tag

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

	def _resolve_method(self, obj, *names):
		'''Different n4d-lliurex-access-control versions have used
		different method name conventions on AccessControlManager
		(snake_case vs camelCase) while keeping the same return shape -
		confirmed by comparing versions 1.12.15 and 1.12.16 in the
		field. Try each candidate name in order and use whichever
		actually exists, instead of assuming one naming convention.'''
		for name in names:
			method = getattr(obj, name, None)
			if callable(method):
				return method
		return None

	#def _resolve_method

	def _user_groups(self, username):
		proc = self._run(["id", "-Gn", username])
		if proc is None or proc.returncode != 0 or not proc.stdout:
			return set()
		return {g.lower() for g in proc.stdout.split()}

	#def _user_groups

	def _check_local_account(self, username, lang):
		'''Requested after noticing that test/admin accounts like
		"bocairent" always get pam_sss code 10 ("unknown user")
		regardless of password, because pam_sss only manages domain
		accounts - local-only accounts are pam_unix's job instead.
		Checking "-s files" specifically (not the default nsswitch
		order) confirms the username resolves via /etc/passwd, i.e. it
		really is a local account, not a coincidentally-similar domain
		one.'''
		proc = self._run(["getent", "-s", "files", "passwd", username])
		if proc is not None and proc.returncode == 0 and proc.stdout.strip():
			return self._tag("local_account", lang)
		return None

	#def _check_local_account

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

		get_users_info = self._resolve_method(acm, "get_users_info", "getUsersInfo")
		try:
			if get_users_info:
				users_info = get_users_info().get("return", {}) or {}
				if users_info.get(clean_user, {}).get("isLocked"):
					return self._tag("local_user_denied", lang)
		except Exception as e:
			print(f"AccessExplainer._check_local_deny_lists (users). Error: {e}")

		user_groups = self._user_groups(username)
		get_groups_info = self._resolve_method(acm, "get_groups_info", "getGroupsInfo")
		if user_groups and get_groups_info:
			try:
				groups_info = get_groups_info().get("return", {}) or {}
				for group_name, group_data in groups_info.items():
					if not isinstance(group_data, dict):
						continue
					if group_data.get("isLocked") and group_name.lower() in user_groups:
						return self._tag("local_group_denied", lang)
			except Exception as e:
				print(f"AccessExplainer._check_local_deny_lists (groups). Error: {e}")

		get_cdc_info = self._resolve_method(acm, "get_cdc_info", "getCDCInfo")
		try:
			if get_cdc_info:
				cdc_info = get_cdc_info().get("return", {}) or {}
				if cdc_info.get("accessControlEnabled") and cdc_info.get("code"):
					allowed = {g.strip().lower() for g in cdc_info["code"].split(",") if g.strip()}
					if allowed and not (user_groups & allowed):
						return self._tag("cdc_denied", lang)
		except Exception as e:
			print(f"AccessExplainer._check_local_deny_lists (cdc). Error: {e}")

		return None

	#def _check_local_deny_lists

	def _check_sssd_service(self, lang):
		proc = self._run(["systemctl", "is-active", "sssd"])
		if proc is not None and proc.stdout.strip() != "active":
			return self._tag("sssd_inactive", lang)
		return None

	#def _check_sssd_service

	def _check_backend_offline(self, minutes, lang):
		proc = self._run(["journalctl", "-u", "sssd", "--since", f"-{minutes}min", "--no-pager"])
		if proc is None or not proc.stdout:
			return None
		lines = [l for l in proc.stdout.splitlines() if "Backend is offline" in l or "Backend is online" in l]
		if lines and "offline" in lines[-1]:
			return self._tag("backend_offline", lang)
		return None

	#def _check_backend_offline

	def _check_pam_log(self, username, minutes, lang):
		proc = self._run(["journalctl", "--since", f"-{minutes}min", "--no-pager", "-g", "pam_sss"])
		if proc is None or not proc.stdout:
			return None
		user_lines = [l for l in proc.stdout.splitlines() if username in l]
		if not user_lines:
			return None

		# Prefer the numeric code (locale-independent) over text matching -
		# see the PAM_SSS_CODE_CATEGORY comment above for why.
		for line in user_lines:
			match = PAM_SSS_RECEIVED_RE.search(line)
			if match:
				category = PAM_SSS_CODE_CATEGORY.get(int(match.group(1)))
				if category:
					return self._tag(category, lang)

		joined = "\n".join(user_lines).lower()
		if "authentication failure" in joined:
			return self._tag("auth_failed", lang)
		if "permission denied" in joined:
			return self._tag("generic", lang)
		return None

	#def _check_pam_log

	def _check_subprocess_based(self, username, minutes, lang):
		'''Runs the sssd/backend/pam-log checks concurrently instead of
		sequentially, bounded by PARALLEL_CHECKS_TIMEOUT, then applies
		the same sssd > backend > pam priority order as before. See the
		module-level comment on PARALLEL_CHECKS_TIMEOUT for why.'''
		checks = {
			"sssd": lambda: self._check_sssd_service(lang),
			"backend": lambda: self._check_backend_offline(minutes, lang),
			"pam": lambda: self._check_pam_log(username, minutes, lang),
		}
		results = {}
		with concurrent.futures.ThreadPoolExecutor(max_workers=len(checks)) as pool:
			futures = {name: pool.submit(fn) for name, fn in checks.items()}
			done, _not_done = concurrent.futures.wait(futures.values(), timeout=PARALLEL_CHECKS_TIMEOUT)
			for name, future in futures.items():
				if future in done:
					try:
						results[name] = future.result()
					except Exception as e:
						print(f"AccessExplainer._check_subprocess_based ({name}). Error: {e}")

		return results.get("sssd") or results.get("backend") or results.get("pam")

	#def _check_subprocess_based

	def _format(self, category, text):
		'''Pilot/debug aid, requested while testing: show which category
		fired right in the on-screen message, so testers don't need to
		check logs to know which branch matched. Optional by design -
		safe to drop this suffix later by changing just this method.'''
		return f"{text} [{category}]"

	#def _format

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
				return n4d.responses.build_successful_call_response(self._format(*self._tag("generic", lang)))

			category, text = (
				self._check_local_deny_lists(username, lang)
				or self._check_local_account(username, lang)
				or self._check_subprocess_based(username, minutes, lang)
				or self._tag("generic", lang)
			)

			return n4d.responses.build_successful_call_response(self._format(category, text))

		except Exception as e:
			print(f"AccessExplainer.explain_login_failure. Error: {e}")
			return n4d.responses.build_successful_call_response(self._format(*self._tag("generic", lang)))

	#def explain_login_failure
