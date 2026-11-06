# Diagnosis: getting into the computer with WifiGva / GVA-Microsoft ID Digital

Analysis date: 2026-11-06
Machine analyzed: `prn5-10366948` (LliureX client, Ubuntu 22.04 Jammy)

## Context

A student logs into the machine with their GVA/Microsoft ID Digital
credentials. Sometimes they authenticate correctly against Active
Directory but are still not allowed to fully get into the machine.
Initial suspicion: a limit on how many devices a single student ID can
log into.

This document records what was found while analyzing (without changing
anything) the real login mechanism on this kind of machine, and serves as
the reference for the diagnostic script `diagnose_login_wifigva.sh`.

## Real architecture found

This machine **does not use classic winbind** for student login: it uses
**SSSD against the `EDU.GVA.ES` domain** (the GVA/Microsoft ID Digital).
The flow is:

1. **Authentication (PAM `auth` phase)**: `pam_sss` validates the
   username/password via Kerberos/LDAP against the central domain
   controller. If this fails, it's simply "wrong password".
2. **Authorization (PAM `account` phase)**: `pam_sss` queries the domain
   again to check whether the *account* is allowed in (locked, expired,
   disabled, access filters, logon hours, etc.). **This is exactly where
   the described symptom happens**: "it validates fine but I'm still not
   let in".
3. In parallel there is a LliureX-specific mechanism, **`cdc-mapper`**
   (local service on `http://localhost:9797`, package `cdc-mapper`), which
   queries LDAP to map AD groups (`ALU_*`, `DOC_*`, `ADM_*`,
   `NODOCENTE_*`) to local groups (`students`, `teachers`, `admins`,
   `NoDocente`...). It is invoked from PAM as an `optional` module
   (`/usr/bin/cdc_trigger_map`), so it **does not block login** even if it
   fails; if it fails, the symptom would be more like "logs in but without
   the expected permissions", not "can't log in at all".
4. There is also a mechanism of **local per-machine denial lists**:
   `/etc/lliurex-access-control/{users-lists,groups-lists}` (and the older
   `login.user.deny` / `login.group.deny` via `pam_listfile`). On this
   machine they were empty, but they can have entries on other machines
   in the school (e.g. a teacher blocking a student on a specific PC).

### Key files/services located

- `/etc/nsswitch.conf` → `passwd/group: files systemd sss [lliurex]`
- `/etc/sssd/sssd.conf` (domain `EDU.GVA.ES`, readable only as root)
- `/usr/share/cdc-mapper/application.py` + `/etc/libnss_lliurex.conf`
  (service `cdc-mapper.service`, port 9797)
- `/etc/lliurex-access-control/{users-lists,groups-lists,cdc-info}`
- `/etc/pam.d/common-auth`, `common-account`, `common-session`

## On the "per-student device limit" hypothesis

In Active Directory, the mechanism closest to a "device limit" is the
**`userWorkstations`** attribute (the "Log On To" tab in the user's
properties), which restricts login to a specific list of computer names.

However, that mechanism is traditionally enforced by **NetLogon**, part of
the Windows/NTLM world. A Linux client using SSSD authenticates directly
via Kerberos/LDAP against the domain controller, and normally **does not
go through that NetLogon check**. So it is unlikely that
`userWorkstations` is the cause of the problem on these LliureX machines -
although it cannot be fully ruled out without read credentials on the
central AD.

More likely candidates, in this specific stack, for "it validates but I'm
not let in":

1. **Account locked out** from failed password attempts (`lockoutTime`) -
   plausible if the student has their old password saved on another
   device (phone, another PC) that keeps retrying in the background.
2. **Access filter** (`ad_access_filter`) or allowed/denied groups
   configured in `sssd.conf` for this school/machine.
3. **SSSD backend intermittently offline** due to the WifiGva network
   itself (observed at boot on this machine: `Backend is offline` →
   `Backend is online` a minute later). If the login attempt lands right
   in that window, it may authenticate from cache but fail the live
   account check.
4. **Local denial list** on that specific machine
   (`/etc/lliurex-access-control/...`).
5. **Expired/disabled account or logon-hours restriction** on the central AD.

If all the local checks (see script) are exhausted and the problem
persists, the next step is to ask whoever administers the central AD
`EDU.GVA.ES` to check, for that specific student:

- `userWorkstations` (list and limit of allowed computers)
- `lockoutTime` (whether the account is locked)
- `logonHours` (time-of-day restrictions)
- The access filter (`ad_access_filter`) or the allowed/denied groups
  applied to this school/machine in `sssd.conf`

## The diagnostic script

File: `diagnose_login_wifigva.sh`

Usage (read-only, makes no changes):

```
sudo ./diagnose_login_wifigva.sh <username> [minutes_back]
```

Example, if the incident happened "just now":

```
sudo ./diagnose_login_wifigva.sh jperez23 30
```

Checks, in order:

1. The machine's authentication mechanism (SSSD vs. winbind, via
   `/etc/nsswitch.conf`).
2. User identity resolution (`getent passwd`, `id`).
3. Status of the SSSD service and the `EDU.GVA.ES` domain
   (`sssctl domain-status`, `sssctl user-checks` if `sssd-tools` is installed).
4. Recent backend offline/online transitions (a hint of WifiGva network
   problems reaching the domain controller).
5. PAM log lines (`pam_sss`, `sssd_be`, `sssd_pam`...) for that user in
   the given time window, with an interpretation of the most common codes
   (user unknown, permission denied, authentication failure...).
6. Local denial lists on that specific machine (user, and also their groups).
7. Status of the `cdc-mapper` group mapping for that user.
8. (With root) Detailed SSSD logs looking for explicit Kerberos errors
   from the domain controller (`KRB5KDC_ERR_*`).
9. A reminder of what to check on the central AD if everything above
   comes back clean.

At the end it prints a **verdict** with the most likely cause detected, or
states that the central Active Directory side needs to be checked.
