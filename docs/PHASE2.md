# Phase 2 - finer-grained causes

## Status: not implemented yet

Phase 2 extends the same `AccessExplainer` plugin from Phase 1 - it is not
a separate component, and it does not touch `Main.qml` again (that patch
is Phase 1's responsibility only).

## What Phase 1 already covers (so Phase 2 doesn't duplicate it)

The original idea for Phase 2 was "explain `lliurex-access-control`
denials in detail". That's already covered by Phase 1's
`_check_local_deny_lists`, which proactively asks `AccessControlManager`
(read-only) before falling back to log scraping - it doesn't depend on
parsing a distinctive log line for that kind of denial, which
`pam_listfile` doesn't reliably produce anyway.

## What's actually left for Phase 2

1. **A more specific sentence per denial mechanism.** Right now
   `_check_local_deny_lists` already distinguishes user-deny / group-deny /
   CDC-allow-list internally and returns a different message for each
   (`local_user_denied`, `local_group_denied`, `cdc_denied` - see
   [MESSAGES.md](MESSAGES.md)). Phase 2's job here, if needed, is only to
   refine wording based on real feedback from the classroom pilot.

2. **Explicit Kerberos errors from the central AD.** `KRB5KDC_ERR_*` codes
   in `/var/log/sssd/sssd_be_EDU.GVA.ES.log` (account locked, password
   expired, policy/time restriction) are the clearest possible signal of a
   central AD decision, but they're only logged if `sssd`'s `debug_level`
   for that domain section is high enough - which is **not** the default.
   Phase 2 adds:
   - A way to raise `debug_level` for the `EDU.GVA.ES` domain section in
     `sssd.conf` (with a backup of the original value and a way to revert
     it - exact mechanism, script vs. extending `scripts/install.sh`, to
     be decided when this is implemented).
   - A new check in `AccessExplainer.py` that greps that log for this
     username and maps the following codes to the planned message
     categories in [MESSAGES.md](MESSAGES.md):
     - `KRB5KDC_ERR_CLIENT_REVOKED` → `kdc_account_locked`
     - `KRB5KDC_ERR_KEY_EXPIRED` → `kdc_password_expired`
     - `KRB5KDC_ERR_POLICY` → `kdc_policy_restriction`

## Explicitly out of scope (see ARCHITECTURE.md for the full reasoning)

No new PAM module (`pam_script.so` or otherwise). If real-world testing
on the pilot shows the journal-scraping approach in Phase 1 is too
unreliable (rotation, delay), that decision gets revisited here - but it
starts as a deliberately rejected option, not a deferred one.

## When to pick this phase up

Only after Phase 1 has been running on this ThinkPad for a while and,
ideally, after enough real `KRB5KDC_ERR_*` cases are actually seen (raising
`debug_level` has its own cost - more verbose logs - so it shouldn't be
turned on speculatively before there's a concrete case to debug).
