"""Unit tests for AccessExplainer, run with plain pytest.

No root, no real N4D server, no network: n4d.server.core and
n4d.responses are stubbed out so AccessExplainer.py can be imported and
exercised in isolation. subprocess.run is monkeypatched per-test to
simulate journalctl/systemctl/id output.

Run with:
    pytest tests/
"""
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "n4d-plugin"))


def _install_n4d_stubs():
    """AccessExplainer.py does `import n4d.responses` and
    `import n4d.server.core as n4dcore` at module level. Those packages
    only exist on a real LliureX/N4D host, so we fake them here."""
    n4d_mod = types.ModuleType("n4d")
    responses_mod = types.ModuleType("n4d.responses")

    def build_successful_call_response(ret_value=True, ret_msg="OK", status_code=0):
        return {"msg": ret_msg, "status": 0, "return": ret_value, "status_code": status_code}

    responses_mod.build_successful_call_response = build_successful_call_response

    server_mod = types.ModuleType("n4d.server")
    core_mod = types.ModuleType("n4d.server.core")

    class _FakeCore:
        @staticmethod
        def get_core():
            return MagicMock()

    core_mod.Core = _FakeCore

    # Manually wire the parent/submodule attributes: when stub modules are
    # inserted straight into sys.modules (instead of going through a real
    # `import`), Python's import machinery never runs the step that would
    # normally set `n4d.responses`/`n4d.server.core` as attributes of their
    # parent package - `import n4d.responses` would otherwise bind the name
    # `n4d` but leave `n4d.responses` undefined, raising AttributeError.
    n4d_mod.responses = responses_mod
    n4d_mod.server = server_mod
    server_mod.core = core_mod

    sys.modules["n4d"] = n4d_mod
    sys.modules["n4d.responses"] = responses_mod
    sys.modules["n4d.server"] = server_mod
    sys.modules["n4d.server.core"] = core_mod


_install_n4d_stubs()

import AccessExplainer as ae_module  # noqa: E402  (import after stubbing)


def make_explainer():
    return ae_module.AccessExplainer()


def fake_proc(stdout="", returncode=0):
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


def test_ping():
    explainer = make_explainer()
    resp = explainer.ping()
    assert resp["return"] is True


def test_msg_defaults_to_es_for_unknown_lang():
    explainer = make_explainer()
    assert explainer._msg("generic", "fr") == ae_module.MESSAGES["generic"]["es"]


def test_msg_picks_ca_when_lang_starts_with_ca():
    explainer = make_explainer()
    assert explainer._msg("generic", "ca_ES") == ae_module.MESSAGES["generic"]["ca"]


def test_msg_picks_en_when_lang_starts_with_en():
    explainer = make_explainer()
    assert explainer._msg("generic", "en_US") == ae_module.MESSAGES["generic"]["en"]


def test_messages_cover_en_es_and_ca_for_every_category():
    for category, bucket in ae_module.MESSAGES.items():
        assert "en" in bucket and bucket["en"], category
        assert "es" in bucket and bucket["es"], category
        assert "ca" in bucket and bucket["ca"], category


def test_messages_loaded_from_sibling_file_not_inlined():
    """The user explicitly asked for i18n to live in its own file, not
    inlined in AccessExplainer.py - this guards that split."""
    import inspect

    source = inspect.getsource(ae_module)
    # category keys like "local_user_denied" legitimately appear as
    # string literals passed to self._tag(...)/self._msg(...) - check for
    # actual message TEXT instead, which should only live in messages.py.
    assert "No puedes entrar con tu cuenta" not in source, "message text got inlined back into AccessExplainer.py"
    assert ae_module.MESSAGES is ae_module._messages_module.MESSAGES


def test_explain_login_failure_empty_username_returns_generic():
    explainer = make_explainer()
    resp = explainer.explain_login_failure("", "es")
    assert resp["return"] == f'{ae_module.MESSAGES["generic"]["es"]} [generic]'


def test_explain_login_failure_never_raises_on_internal_error():
    explainer = make_explainer()
    explainer.core.get_plugin.side_effect = RuntimeError("boom")
    with patch.object(ae_module.AccessExplainer, "_run", side_effect=RuntimeError("boom")):
        resp = explainer.explain_login_failure("someuser", "es")
    assert resp["return"] == f'{ae_module.MESSAGES["generic"]["es"]} [generic]'


def test_local_account_detected():
    """Real-world case: "bocairent" and similar local/admin accounts
    always get pam_sss code 10 (unknown user) regardless of password,
    because pam_sss only manages domain accounts. Detecting that the
    username resolves via /etc/passwd specifically ("-s files") lets
    the message say so explicitly instead of the misleading generic
    "unknown user" wording."""
    explainer = make_explainer()
    with patch.object(explainer, "_run", return_value=fake_proc(stdout="bocairent:x:1002:1002::/home/bocairent:/bin/bash\n")):
        assert explainer._check_local_account("bocairent", "es") == ("local_account", ae_module.MESSAGES["local_account"]["es"])


def test_local_account_not_found_returns_none():
    explainer = make_explainer()
    with patch.object(explainer, "_run", return_value=fake_proc(stdout="", returncode=2)):
        assert explainer._check_local_account("danmilfer", "es") is None


def test_local_account_checked_before_subprocess_based_checks():
    """Priority: a local account should be reported as such even if
    sssd/backend/pam checks would otherwise have something to say."""
    explainer = make_explainer()
    explainer.core.get_plugin.return_value = None  # no local deny-list match
    with patch.object(explainer, "_check_local_account", return_value=("local_account", ae_module.MESSAGES["local_account"]["es"])), \
         patch.object(explainer, "_check_subprocess_based", return_value=("generic", ae_module.MESSAGES["generic"]["es"])):
        resp = explainer.explain_login_failure("bocairent", "es")
    assert resp["return"] == f'{ae_module.MESSAGES["local_account"]["es"]} [local_account]'


def test_sssd_inactive_detected():
    explainer = make_explainer()
    with patch.object(explainer, "_run", return_value=fake_proc(stdout="inactive\n")):
        assert explainer._check_sssd_service("es") == ("sssd_inactive", ae_module.MESSAGES["sssd_inactive"]["es"])


def test_sssd_active_returns_none():
    explainer = make_explainer()
    with patch.object(explainer, "_run", return_value=fake_proc(stdout="active\n")):
        assert explainer._check_sssd_service("es") is None


def test_backend_offline_last_transition_is_offline():
    explainer = make_explainer()
    journal = (
        "nov 06 09:09:17 host sssd_be[1]: Backend is online\n"
        "nov 06 09:10:00 host sssd_be[1]: Backend is offline\n"
    )
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_backend_offline(10, "es") == ("backend_offline", ae_module.MESSAGES["backend_offline"]["es"])


def test_backend_offline_last_transition_is_online_returns_none():
    explainer = make_explainer()
    journal = (
        "nov 06 09:09:17 host sssd_be[1]: Backend is offline\n"
        "nov 06 09:10:00 host sssd_be[1]: Backend is online\n"
    )
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_backend_offline(10, "es") is None


def test_pam_log_user_unknown_by_numeric_code():
    """Real-world wording from the field is 'User not known to the
    underlying authentication module' (English) or 'Usuari desconegut
    per al modul d'autenticacio subjacent' (Catalan) - neither contains
    the literal substring "user unknown". Every failed attempt, known
    or unknown user, also logs a separate "authentication failure" line
    regardless of cause. Matching the numeric code (10) is what actually
    distinguishes "unknown user" from "wrong password for a real user"
    reliably, independent of system locale."""
    explainer = make_explainer()
    journal = (
        "nov 06 15:35:19 host sddm-helper[1]: pam_sss(sddm:auth): authentication failure; "
        "logname= uid=0 euid=0 tty= ruser= rhost= user=eduardo\n"
        "nov 06 15:35:19 host sddm-helper[1]: pam_sss(sddm:auth): received for user eduardo: "
        "10 (User not known to the underlying authentication module)\n"
    )
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_pam_log("eduardo", 10, "es") == ("user_unknown", ae_module.MESSAGES["user_unknown"]["es"])


def test_pam_log_authentication_failure_by_numeric_code():
    """A real existing account with a wrong password logs code 7, not
    10 - confirmed in the field (user "marmilfer", code 7, "Error
    d'autenticacio")."""
    explainer = make_explainer()
    journal = (
        "nov 06 15:45:42 host sddm-helper[1]: pam_sss(sddm:auth): authentication failure; "
        "logname= uid=0 euid=0 tty= ruser= rhost= user=marmilfer\n"
        "nov 06 15:45:42 host sddm-helper[1]: pam_sss(sddm:auth): received for user marmilfer: "
        "7 (Authentication error)\n"
    )
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_pam_log("marmilfer", 10, "es") == ("auth_failed", ae_module.MESSAGES["auth_failed"]["es"])


def test_pam_log_unrecognized_code_falls_back_to_text_match():
    """A pam_sss code this project hasn't mapped (e.g. 9, "authentication
    service cannot retrieve information") falls back to the old
    substring match on "authentication failure" instead of being lost."""
    explainer = make_explainer()
    journal = (
        "nov 06 16:07:57 host sddm-helper[1]: pam_sss(sddm:auth): authentication failure; "
        "logname= uid=0 euid=0 tty= ruser= rhost= user=me.millan\n"
        "nov 06 16:07:57 host sddm-helper[1]: pam_sss(sddm:auth): received for user me.millan: "
        "9 (Authentication service cannot retrieve user credentials)\n"
    )
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_pam_log("me.millan", 10, "es") == ("auth_failed", ae_module.MESSAGES["auth_failed"]["es"])


def test_pam_log_no_lines_for_user_returns_none():
    explainer = make_explainer()
    journal = "nov 06 10:00:00 host sudo[1]: pam_sss(sudo:auth): authentication failure; user=someoneelse\n"
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_pam_log("bob", 10, "es") is None


def test_local_user_denied():
    explainer = make_explainer()
    acm = MagicMock()
    acm.get_users_info.return_value = {"return": {"bob": {"isLocked": True}}}
    acm.get_groups_info.return_value = {"return": {}}
    acm.get_cdc_info.return_value = {"return": {"accessControlEnabled": False}}
    explainer.core.get_plugin.return_value = acm
    with patch.object(explainer, "_user_groups", return_value=set()):
        reason = explainer._check_local_deny_lists("bob", "es")
    assert reason == ("local_user_denied", ae_module.MESSAGES["local_user_denied"]["es"])


def test_local_group_denied():
    explainer = make_explainer()
    acm = MagicMock()
    acm.get_users_info.return_value = {"return": {}}
    acm.get_groups_info.return_value = {"return": {"alu_eso_a3": {"isLocked": True}}}
    acm.get_cdc_info.return_value = {"return": {"accessControlEnabled": False}}
    explainer.core.get_plugin.return_value = acm
    with patch.object(explainer, "_user_groups", return_value={"alu_eso_a3"}):
        reason = explainer._check_local_deny_lists("bob", "es")
    assert reason == ("local_group_denied", ae_module.MESSAGES["local_group_denied"]["es"])


def test_cdc_denied_when_user_has_no_allowed_group():
    explainer = make_explainer()
    acm = MagicMock()
    acm.get_users_info.return_value = {"return": {}}
    acm.get_groups_info.return_value = {"return": {}}
    acm.get_cdc_info.return_value = {
        "return": {"accessControlEnabled": True, "code": "grp_allowed,adminsai"}
    }
    explainer.core.get_plugin.return_value = acm
    with patch.object(explainer, "_user_groups", return_value={"alu_eso_a3"}):
        reason = explainer._check_local_deny_lists("bob", "es")
    assert reason == ("cdc_denied", ae_module.MESSAGES["cdc_denied"]["es"])


def test_cdc_allowed_when_user_has_allowed_group_returns_none():
    explainer = make_explainer()
    acm = MagicMock()
    acm.get_users_info.return_value = {"return": {}}
    acm.get_groups_info.return_value = {"return": {}}
    acm.get_cdc_info.return_value = {
        "return": {"accessControlEnabled": True, "code": "grp_allowed,adminsai"}
    }
    explainer.core.get_plugin.return_value = acm
    with patch.object(explainer, "_user_groups", return_value={"grp_allowed"}):
        reason = explainer._check_local_deny_lists("bob", "es")
    assert reason is None


def test_subprocess_checks_run_in_parallel_not_sequentially():
    """Real-world case: right after a system update, journalctl got slow
    enough that two sequential SUBPROCESS_TIMEOUT waits (sssd backend +
    pam log, each hitting the timeout) added up and exceeded the N4D
    client's own read timeout. _check_subprocess_based must run the
    three checks concurrently, so worst case is close to one
    SUBPROCESS_TIMEOUT, not their sum."""
    explainer = make_explainer()

    def slow_run(cmd):
        time.sleep(ae_module.SUBPROCESS_TIMEOUT * 0.8)
        # "active" satisfies the sssd check as healthy, and contains
        # nothing that the backend/pam-log checks would match on either.
        return fake_proc(stdout="active")

    start = time.monotonic()
    with patch.object(explainer, "_run", side_effect=slow_run):
        reason = explainer._check_subprocess_based("someuser", 10, "es")
    elapsed = time.monotonic() - start

    assert reason is None
    assert elapsed < ae_module.SUBPROCESS_TIMEOUT * 1.6, (
        f"took {elapsed:.2f}s - checks are not running in parallel"
    )


def test_local_user_denied_via_camel_case_legacy_api():
    """Real-world case found on n4d-lliurex-access-control 1.12.15:
    AccessControlManager only exposes getUsersInfo/getGroupsInfo/getCDCInfo
    (camelCase), not the newer get_users_info/get_groups_info/get_cdc_info
    (snake_case). A plain object with only the legacy spelling must still
    resolve and work, exactly like the 1.12.16 (snake_case) case above."""

    class LegacyAccessControlManager:
        def getUsersInfo(self):
            return {"return": {"bob": {"isLocked": True}}}

        def getGroupsInfo(self):
            return {"return": {}}

        def getCDCInfo(self):
            return {"return": {"accessControlEnabled": False}}

    explainer = make_explainer()
    explainer.core.get_plugin.return_value = LegacyAccessControlManager()
    with patch.object(explainer, "_user_groups", return_value=set()):
        reason = explainer._check_local_deny_lists("bob", "es")
    assert reason == ("local_user_denied", ae_module.MESSAGES["local_user_denied"]["es"])


def test_resolve_method_prefers_first_existing_name():
    class Obj:
        def camel(self):
            return "camel"

    explainer = make_explainer()
    resolved = explainer._resolve_method(Obj(), "snake", "camel")
    assert resolved() == "camel"


def test_resolve_method_returns_none_when_neither_name_exists():
    class Obj:
        pass

    explainer = make_explainer()
    assert explainer._resolve_method(Obj(), "snake", "camel") is None


def test_local_deny_lists_never_raises_when_access_control_manager_missing():
    explainer = make_explainer()
    explainer.core.get_plugin.return_value = None
    assert explainer._check_local_deny_lists("bob", "es") is None


def test_local_deny_lists_never_raises_on_write_method_only_reads_used():
    """Hard guarantee from docs/RISKS.md: AccessExplainer must never call
    set_cdc_info / disable_access_denied_cdc (they restart sssd)."""
    import inspect

    source = inspect.getsource(ae_module.AccessExplainer._check_local_deny_lists)
    assert "set_cdc_info" not in source
    assert "disable_access_denied_cdc" not in source
    assert "set_users_info" not in source
    assert "set_groups_info" not in source
