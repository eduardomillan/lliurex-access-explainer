#!/usr/bin/env bash
#
# diagnose_login_wifigva.sh
#
# Diagnosis of "getting into the computer" for students with a GVA
# Microsoft/ID Digital account, on LliureX machines joined to the
# EDU.GVA.ES domain via SSSD.
#
# What it does:
#   When a student's password validates but they're still not let into
#   the computer (the login screen rejects them anyway), this script
#   collects, in order:
#     1) whether this machine uses SSSD or winbind to resolve identity
#     2) whether the user is recognized by the system (getent/id)
#     3) status of the sssd service and the EDU.GVA.ES domain
#     4) recent connection drops to the domain controller
#        (backend offline/online), a typical cause tied to the WifiGva network
#     5) PAM/SSSD log lines for that user in the given time window,
#        interpreting the most common error codes
#     6) whether the user or any of their groups is on a local denial
#        list on THIS machine (lliurex-access-control)
#     7) whether the group mapping (cdc-mapper: students/teachers/admins)
#        was done correctly for that user
#     8) (root only) detailed SSSD logs looking for explicit Kerberos
#        errors returned by the domain controller
#     9) a note on the "device limit" hypothesis (AD's userWorkstations
#        attribute) and what to check on the central AD if everything
#        above comes back clean
#   At the end it prints a VERDICT with the most likely cause detected.
#
# MAKES NO CHANGES. Only reads logs, service status, and configuration.
#
# Usage:
#   sudo ./diagnose_login_wifigva.sh <username> [minutes_back]
#   ./diagnose_login_wifigva.sh -h | --help
#
#   <username>      the affected student's username (ID Digital), exactly
#                     as it appears at login (without @domain)
#   [minutes_back]  how far back to search the logs, in minutes (default
#                     60). Use a value close to when the incident actually
#                     happened, to avoid getting lost among other users' logs.
#
# Requires sudo/root to read /var/log/sssd/* and some journalctl entries;
# without root the diagnosis is partial but still useful.
#
# Examples:
#   sudo ./diagnose_login_wifigva.sh jperez23 30
#       -> student jperez23 says this happened "just now"
#   sudo ./diagnose_login_wifigva.sh mgarcia10 480
#       -> the incident happened earlier this morning, several hours ago
#
set -uo pipefail

show_help() {
    sed -n '2,/^set -uo pipefail/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
esac

USER_IN="${1:-}"
MINUTES="${2:-60}"

if [[ -z "$USER_IN" ]]; then
    echo "Usage: $0 <username> [minutes_back]"
    echo "       $0 -h | --help    (for more information)"
    exit 1
fi

IS_ROOT=0
[[ "$(id -u)" -eq 0 ]] && IS_ROOT=1

SEP() { printf '\n==================== %s ====================\n' "$1"; }
WARN() { printf '  [!] %s\n' "$1"; }
INFO() { printf '  - %s\n' "$1"; }
OK()   { printf '  [OK] %s\n' "$1"; }

VERDICT=()
add_verdict() { VERDICT+=("$1"); }

echo "WifiGva login diagnosis / GVA-Microsoft ID Digital"
echo "User analyzed      : $USER_IN"
echo "Time window         : last $MINUTES minutes"
echo "Running as root     : $([[ $IS_ROOT -eq 1 ]] && echo yes || echo no)"
[[ $IS_ROOT -eq 0 ]] && WARN "No root privileges: /var/log/sssd/* and some journalctl entries won't be readable. Re-run with sudo for a complete diagnosis."

#------------------------------------------------------------------
SEP "1. Authentication mechanism detected on this machine"
#------------------------------------------------------------------
USES_SSSD=0
USES_WINBIND=0
grep -Eq '^\s*passwd:.*\bsss\b' /etc/nsswitch.conf 2>/dev/null && USES_SSSD=1
grep -Eq '^\s*passwd:.*\bwinbind\b' /etc/nsswitch.conf 2>/dev/null && USES_WINBIND=1

if [[ $USES_SSSD -eq 1 ]]; then
    OK "This machine resolves identity via SSSD (/etc/nsswitch.conf -> passwd: ... sss)"
elif [[ $USES_WINBIND -eq 1 ]]; then
    OK "This machine resolves identity via winbind (/etc/nsswitch.conf -> passwd: ... winbind)"
    WARN "This script is designed for LliureX machines using SSSD. With winbind, check instead: wbinfo -t, wbinfo -i <user>, net ads info, net ads testjoin, and 'wbinfo -a user%password'."
else
    WARN "Neither sss nor winbind detected in /etc/nsswitch.conf. This machine may use another mechanism (direct LDAP, plain krb5, etc.)."
fi

if grep -q 'lliurex' /etc/nsswitch.conf 2>/dev/null; then
    INFO "The 'lliurex' NSS module (cdc-mapper) is also in use, mapping EDU.GVA.ES AD groups (ALU/DOC/ADM/NODOCENTE) to local groups (students/teachers/admins/...)."
fi

#------------------------------------------------------------------
SEP "2. User identity resolution"
#------------------------------------------------------------------
GETENT_OUT="$(getent passwd "$USER_IN" 2>&1)"
if [[ -z "$GETENT_OUT" ]]; then
    WARN "getent passwd '$USER_IN' returns nothing: the identity system does NOT recognize this user on this machine right now."
    add_verdict "NSS/SSSD cannot resolve the user's identity on this machine (possible backend outage, a typo in the username, or the user has never logged in here before and there is no cache)."
else
    OK "getent passwd: $GETENT_OUT"
fi

ID_OUT="$(id "$USER_IN" 2>&1)"
echo "  id $USER_IN -> $ID_OUT"

#------------------------------------------------------------------
SEP "3. SSSD service and EDU.GVA.ES domain status"
#------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1 && systemctl list-units --type=service 2>/dev/null | grep -q sssd; then
    SSSD_ACTIVE="$(systemctl is-active sssd 2>/dev/null)"
    echo "  sssd service status: $SSSD_ACTIVE"
    [[ "$SSSD_ACTIVE" != "active" ]] && { WARN "sssd is not active on this machine."; add_verdict "The sssd service is not active on this machine: no domain login can succeed."; }

    if command -v sssctl >/dev/null 2>&1; then
        echo
        echo "  -- sssctl domain-status --"
        sssctl domain-status EDU.GVA.ES 2>&1 | sed 's/^/  /'
        echo
        echo "  -- sssctl user-checks $USER_IN -a auth --"
        sssctl user-checks "$USER_IN" -a auth 2>&1 | sed 's/^/  /'
    else
        INFO "sssctl is not installed on this machine (package sssd-tools). Install it for a more direct diagnosis: apt install sssd-tools"
    fi
else
    INFO "sssd does not appear to be present as a systemd service on this machine."
fi

#------------------------------------------------------------------
SEP "4. Recent backend offline/online transitions (WifiGva network / DC)"
#------------------------------------------------------------------
if command -v journalctl >/dev/null 2>&1; then
    OFFLINE_EVENTS="$(journalctl -u sssd --since "-${MINUTES}min" --no-pager 2>/dev/null | grep -E 'Backend is (offline|online)')"
    if [[ -n "$OFFLINE_EVENTS" ]]; then
        echo "$OFFLINE_EVENTS" | sed 's/^/  /'
        if echo "$OFFLINE_EVENTS" | tail -1 | grep -q offline; then
            WARN "The SSSD backend went 'offline' during the analyzed window, with no record of coming back 'online' afterwards."
            add_verdict "The machine lost contact with the domain controller (unstable WifiGva network, DNS, or an unreachable DC) during the analyzed window: this can authenticate with cached credentials but then deny the 'account' phase because the account status can't be confirmed."
        fi
    else
        INFO "No sssd offline/online transitions in the last $MINUTES minutes (or the journal has rotated)."
    fi
else
    INFO "journalctl not available."
fi

#------------------------------------------------------------------
SEP "5. Login/PAM entries for '$USER_IN' in the last $MINUTES min"
#------------------------------------------------------------------
if command -v journalctl >/dev/null 2>&1; then
    LOG_LINES="$(journalctl --since "-${MINUTES}min" --no-pager 2>/dev/null | grep -iE "pam_sss|sssd_be|sssd_pam|sssd_nss|sddm|lightdm|gdm" | grep -F "$USER_IN")"
    if [[ -z "$LOG_LINES" ]]; then
        WARN "No pam_sss/sssd/session-manager log lines mentioning '$USER_IN' were found in the last $MINUTES minutes."
        INFO "Try widening the window: $0 $USER_IN 240"
    else
        echo "$LOG_LINES" | sed 's/^/  /'
        echo
        echo "  -- Interpretation of the most common pam_sss codes --"
        echo "$LOG_LINES" | grep -oE '\b[0-9]+ \([^)]*\)' | sort -u | while read -r code; do
            echo "    code seen: $code"
        done
        echo "$LOG_LINES" | grep -qi 'user unknown\|desconegut' && {
            WARN "pam_sss returns 'user unknown': this machine does not recognize that account in the domain right now (this can be a temporary SSSD/backend outage, not a missing 'device slot')."
            add_verdict "pam_sss reports 'user unknown' (PAM_USER_UNKNOWN): this is not an account rejection, it means the backend could not resolve the user at that moment (see section 4, backend offline)."
        }
        echo "$LOG_LINES" | grep -qi 'permission denied\|denegad' && {
            WARN "pam_sss returns 'permission denied' in the account phase: the account authenticated successfully but was rejected by a restriction (disabled/expired account, access filter, logon hours, etc.)."
            add_verdict "The 'account' phase of pam_sss explicitly denies access (PAM_PERM_DENIED). Check on the domain controller: locked, expired, or disabled account, an access filter (ad_access_filter), or allowed/denied groups."
        }
        echo "$LOG_LINES" | grep -qi 'authentication failure' && {
            WARN "Authentication failures (credentials) are logged for this user."
            add_verdict "There were authentication failures (wrong password/credential) in addition to, or instead of, a plain account rejection. Check with the student whether they typed the ID Digital password correctly."
        }
    fi
else
    INFO "journalctl not available; check /var/log/auth.log instead."
fi

#------------------------------------------------------------------
SEP "6. Local access lists on this machine (lliurex-access-control)"
#------------------------------------------------------------------
ACL_DIR="/etc/lliurex-access-control"
if [[ -d "$ACL_DIR" ]]; then
    FOUND_DENY=0
    for f in "$ACL_DIR"/users-lists/* "$ACL_DIR"/groups-lists/* "$ACL_DIR"/login.user.deny "$ACL_DIR"/login.group.deny; do
        [[ -f "$f" ]] || continue
        if grep -qiE "^\s*${USER_IN}\s*$" "$f" 2>/dev/null; then
            WARN "User '$USER_IN' literally appears in $f"
            add_verdict "The user is on a local denial list on THIS machine ($f). This blocks login on this specific machine, it is not a global device limit."
            FOUND_DENY=1
        fi
        # also check whether any of the user's groups is on a group list
        if [[ "$f" == *groups-lists* || "$f" == *login.group.deny ]]; then
            for g in $(id -Gn "$USER_IN" 2>/dev/null); do
                if grep -qiE "^\s*${g}\s*$" "$f" 2>/dev/null; then
                    WARN "The user's group '$g' appears in $f"
                    add_verdict "One of the user's groups ($g) is locally denied on this machine via $f."
                    FOUND_DENY=1
                fi
            done
        fi
    done
    [[ $FOUND_DENY -eq 0 ]] && OK "The user and their groups do not appear in any local denial list on this machine."
else
    INFO "This machine does not have $ACL_DIR (it does not use lliurex-access-control local access lists)."
fi

#------------------------------------------------------------------
SEP "7. CDC group mapping (students/teachers/admins) for this user"
#------------------------------------------------------------------
if systemctl is-active --quiet cdc-mapper 2>/dev/null; then
    OK "cdc-mapper service is active."
    GRALL="$(curl -s --max-time 5 http://localhost:9797/getgrall 2>/dev/null)"
    if [[ -n "$GRALL" ]]; then
        if echo "$GRALL" | grep -q "\"$USER_IN\""; then
            OK "The user appears in cdc-mapper's group cache:"
            echo "$GRALL" | tr ',' '\n' | grep -B2 "\"$USER_IN\"" | sed 's/^/    /' | head -20
        else
            WARN "The user does NOT appear in any cdc-mapper group yet."
            INFO "This alone doesn't block login (the LDAP group lookup is 'optional' in PAM), but it may mean that, even when the login succeeds, the student doesn't get the expected permissions (e.g. not recognized as 'students'). If the real symptom is a 'wrong profile/permissions' rather than 'can't log in', look here."
        fi
    else
        WARN "Could not query http://localhost:9797/getgrall (cdc-mapper service is not responding)."
    fi
else
    INFO "cdc-mapper is not active on this machine (or not installed)."
fi

#------------------------------------------------------------------
SEP "8. Detailed SSSD logs (requires root) and Kerberos errors"
#------------------------------------------------------------------
if [[ $IS_ROOT -eq 1 ]]; then
    SSSD_LOG_DIR="/var/log/sssd"
    if [[ -d "$SSSD_LOG_DIR" ]]; then
        for logf in "$SSSD_LOG_DIR"/sssd_pam.log "$SSSD_LOG_DIR"/sssd_nss.log "$SSSD_LOG_DIR"/sssd_*EDU*.log "$SSSD_LOG_DIR"/sssd_be_EDU.GVA.ES.log; do
            [[ -f "$logf" ]] || continue
            MATCHES="$(grep -i "$USER_IN" "$logf" 2>/dev/null | tail -40)"
            if [[ -n "$MATCHES" ]]; then
                echo "  -- $logf --"
                echo "$MATCHES" | sed 's/^/    /'
                echo "$MATCHES" | grep -qiE 'KRB5KDC_ERR|KDC_ERR' && {
                    WARN "Explicit Kerberos errors from the domain controller were found for this user (see above)."
                    add_verdict "The domain controller (KDC) itself returns an explicit Kerberos error for this account (locked/expired/policy-restricted account). Check the exact KRB5KDC_ERR_* code above: it states the real reason given by the central AD EDU.GVA.ES."
                }
            fi
        done
    else
        INFO "$SSSD_LOG_DIR does not exist, or debug logging is not enabled (sssd.conf: debug_level)."
    fi
else
    WARN "Without root, /var/log/sssd/* cannot be read. Re-run with sudo to see the Kerberos/LDAP detail from the domain controller."
fi

#------------------------------------------------------------------
SEP "9. On the 'per-student device limit' hypothesis"
#------------------------------------------------------------------
cat <<'EOF'
  In Active Directory, the mechanism closest to a "device limit" is the
  userWorkstations attribute (the "Log On To" tab in the user's
  properties), which restricts login to a specific list of computer
  names. However, on a Linux/LliureX client using SSSD, login normally
  does NOT go through NetLogon (the mechanism Windows uses to enforce
  that restriction); SSSD authenticates directly via Kerberos/LDAP
  against the DC, so userWorkstations is almost never the cause of a
  login failure on these machines. This script cannot query that
  attribute without read credentials on the central AD EDU.GVA.ES: if
  everything above comes back clean and the problem persists, ask whoever
  administers the central AD to check, for that student:
    - userWorkstations (list and limit of allowed computers)
    - whether the account is locked out from failed attempts (lockoutTime)
    - logonHours / time-of-day restrictions
    - whether there is an access filter (ad_access_filter) or an
      allowed/denied group applied to this school or this machine in sssd.conf
EOF

#------------------------------------------------------------------
SEP "VERDICT"
#------------------------------------------------------------------
if [[ ${#VERDICT[@]} -eq 0 ]]; then
    echo "  No clear cause was detected on this machine with the available data."
    echo "  Review section 9 and check the central Active Directory side (EDU.GVA.ES)."
else
    i=1
    for v in "${VERDICT[@]}"; do
        echo "  $i) $v"
        i=$((i+1))
    done
fi
echo
