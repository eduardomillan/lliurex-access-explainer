"""Unit tests for AccessExplainer, run with plain pytest.

No root, no real N4D server, no network: n4d.server.core and
n4d.responses are stubbed out so AccessExplainer.py can be imported and
exercised in isolation. subprocess.run is monkeypatched per-test to
simulate journalctl/systemctl/id output.

Run with:
    pytest tests/
"""
import sys
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


def test_messages_cover_es_and_ca_for_every_category():
    for category, bucket in ae_module.MESSAGES.items():
        assert "es" in bucket and bucket["es"], category
        assert "ca" in bucket and bucket["ca"], category


def test_msg_defaults_to_es_for_unknown_lang():
    explainer = make_explainer()
    assert explainer._msg("generic", "fr") == ae_module.MESSAGES["generic"]["es"]


def test_msg_picks_ca_when_lang_starts_with_ca():
    explainer = make_explainer()
    assert explainer._msg("generic", "ca_ES") == ae_module.MESSAGES["generic"]["ca"]


def test_explain_login_failure_empty_username_returns_generic():
    explainer = make_explainer()
    resp = explainer.explain_login_failure("", "es")
    assert resp["return"] == ae_module.MESSAGES["generic"]["es"]


def test_explain_login_failure_never_raises_on_internal_error():
    explainer = make_explainer()
    explainer.core.get_plugin.side_effect = RuntimeError("boom")
    with patch.object(ae_module.AccessExplainer, "_run", side_effect=RuntimeError("boom")):
        resp = explainer.explain_login_failure("someuser", "es")
    assert resp["return"] == ae_module.MESSAGES["generic"]["es"]


def test_sssd_inactive_detected():
    explainer = make_explainer()
    with patch.object(explainer, "_run", return_value=fake_proc(stdout="inactive\n")):
        assert explainer._check_sssd_service("es") == ae_module.MESSAGES["sssd_inactive"]["es"]


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
        assert explainer._check_backend_offline(10, "es") == ae_module.MESSAGES["backend_offline"]["es"]


def test_backend_offline_last_transition_is_online_returns_none():
    explainer = make_explainer()
    journal = (
        "nov 06 09:09:17 host sssd_be[1]: Backend is offline\n"
        "nov 06 09:10:00 host sssd_be[1]: Backend is online\n"
    )
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_backend_offline(10, "es") is None


def test_pam_log_user_unknown():
    explainer = make_explainer()
    journal = "nov 06 10:00:00 host sudo[1]: pam_sss(sudo:auth): received for user alice: 10 (User unknown)\n"
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_pam_log("alice", 10, "es") == ae_module.MESSAGES["user_unknown"]["es"]


def test_pam_log_authentication_failure():
    explainer = make_explainer()
    journal = "nov 06 10:00:00 host sudo[1]: pam_sss(sudo:auth): authentication failure; user=bob\n"
    with patch.object(explainer, "_run", return_value=fake_proc(stdout=journal)):
        assert explainer._check_pam_log("bob", 10, "es") == ae_module.MESSAGES["auth_failed"]["es"]


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
    assert reason == ae_module.MESSAGES["local_user_denied"]["es"]


def test_local_group_denied():
    explainer = make_explainer()
    acm = MagicMock()
    acm.get_users_info.return_value = {"return": {}}
    acm.get_groups_info.return_value = {"return": {"alu_eso_a3": {"isLocked": True}}}
    acm.get_cdc_info.return_value = {"return": {"accessControlEnabled": False}}
    explainer.core.get_plugin.return_value = acm
    with patch.object(explainer, "_user_groups", return_value={"alu_eso_a3"}):
        reason = explainer._check_local_deny_lists("bob", "es")
    assert reason == ae_module.MESSAGES["local_group_denied"]["es"]


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
    assert reason == ae_module.MESSAGES["cdc_denied"]["es"]


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
