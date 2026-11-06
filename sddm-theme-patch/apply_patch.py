#!/usr/bin/env python3
"""Generate Main.qml.patched from Main.qml.pristine.

Applies three additive changes needed to show AccessExplainer messages on
login failure, anchored on exact substrings (or a tightly-scoped regex for
the one spot with stray trailing whitespace) so the script fails loudly
instead of silently mis-patching if a new theme version changes the
surrounding code.
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "Main.qml.pristine"
DST = HERE / "Main.qml.patched"
PROJECT_VERSION = (HERE.parent / "VERSION").read_text().strip()

ANCHOR_1 = '''    function showWarning(msg)
    {
        message.type = Kirigami.MessageType.Warning;
        message.text = msg;
        message.visible = true;
        //root.topWindow = loginFrame;
        root.topWindow.enabled = true;
    }

'''
INSERT_1 = '''    function explainerLang()
    {
        // AccessExplainer: pick the message language from the greeter locale.
        // Qt.locale().name is a PROPERTY (e.g. "es_ES"/"ca_ES"), not a method -
        // calling it as name() throws "Property 'name' ... is not a function"
        // and aborts onLoginFailed() before the N4D call ever runs.
        var n = Qt.locale().name;
        return n.indexOf("ca") === 0 ? "ca" : "es";
    }

'''

ANCHOR_2 = '''    N4D.Proxy
    {
        id: local_get_active_connections
        client: n4dLocal
        plugin: "WifiEduGva"
        method: "get_active_connections"

        onError: {
            console.log("Failed to list active connections");
            showError(i18nd("lliurex-sddm-theme","Failed to establish an internet connection"));
        }

        onResponse: {
            console.log("connections: ", value.count);
            if (value.count==0) {
                showError(i18nd("lliurex-sddm-theme","Failed to establish an internet connection"));
            }
            else {
                showError(i18nd("lliurex-sddm-theme","No connection to server"));
            }
        }
    }

'''
INSERT_2 = '''    N4D.Proxy
    {
        // AccessExplainer (lliurex-access-explainer project): ask the local
        // N4D plugin for a human-readable reason right after a login
        // failure, reusing the same pattern WifiEduGva already uses above.
        id: local_explain_login_failure
        client: n4dLocal
        plugin: "AccessExplainer"
        method: "explain_login_failure"

        onError: {
            console.log("AccessExplainer: no response, falling back to the generic message");
            showError(i18nd("lliurex-sddm-theme","Login failed"));
        }

        onResponse: {
            showError(value);
        }
    }

    N4D.Proxy
    {
        // AccessExplainer: fetch the configured auto-hide delay once at
        // startup; explainerDisplayMs keeps its safe default if this
        // fails or never returns (see get_display_seconds() in
        // AccessExplainer.py and DISPLAY_SECONDS_CONFIG_FILE there for
        // how to change the default without re-patching this file).
        id: local_get_display_seconds
        client: n4dLocal
        plugin: "AccessExplainer"
        method: "get_display_seconds"

        onError: {
            console.log("AccessExplainer: failed to fetch display_seconds, keeping default");
        }

        onResponse: {
            root.explainerDisplayMs = value * 1000;
        }
    }

    N4D.Proxy
    {
        // AccessExplainer: Ethernet/Wi-Fi IPs for the status bar, so a
        // machine can be identified at a glance when helping remotely.
        // value is a list of {iface, type, ip} - see get_network_info()
        // in AccessExplainer.py for how virtual interfaces are excluded.
        id: local_get_network_info
        client: n4dLocal
        plugin: "AccessExplainer"
        method: "get_network_info"

        onError: {
            console.log("AccessExplainer: failed to fetch network info");
        }

        onResponse: {
            var parts = [];
            for (var n = 0; n < value.length; n++) {
                parts.push(value[n].iface + ": " + value[n].ip);
            }
            root.explainerNetworkInfo = parts.join("  ·  ");
        }
    }

'''

# Anchor 3 is matched with a regex (not a literal string) because the
# pristine source has a line with trailing whitespace between the two
# statements that is easy to mistranscribe by hand.
ANCHOR_3_RE = re.compile(
    r'        function onLoginFailed\(\) \{\n'
    r'            showError\(i18nd\("lliurex-sddm-theme","Login failed"\)\);\n'
    r'[ \t]*\n'
    r'            loginFrame\.enabled=true;\n'
    r'            txtPass\.text = "";\n'
    r'            txtPass\.focus = true;\n'
    r'        \}'
)
INSERT_3 = '''        function onLoginFailed() {
            // AccessExplainer: show a transient message while we ask the
            // local N4D plugin for the real reason; onError/onResponse of
            // local_explain_login_failure take over from here.
            showWarning(i18nd("lliurex-sddm-theme","Checking the reason for the failure..."));
            local_explain_login_failure.call([txtUser.text, explainerLang()]);

            loginFrame.enabled=true;
            txtPass.text = "";
            txtPass.focus = true;
        }'''

# Anchor 4, also regex-matched for the same blank-line-whitespace reason as
# anchor 3: the message box's wrapping Item had a fixed height:32 and the
# InlineMessage used anchors.fill:parent, which forces its actual height to
# that fixed 32px. Kirigami.InlineMessage's own docs say to avoid setting
# its height and let it manage its own implicitHeight - our messages are
# 1-2 full sentences, longer than the theme's original short strings
# ("Login failed"), and got clipped to only their tail end as a result.
ANCHOR_4_RE = re.compile(
    r'            Item \{\n'
    r'                Layout\.fillWidth:true;\n'
    r'                height:32\n'
    r'[ \t]*\n'
    r'                Kirigami\.InlineMessage \{\n'
    r'                    id: message\n'
    r'                    anchors\.fill:parent\n'
    r'                    showCloseButton: true\n'
    r'[ \t]*\n'
    r'                \}\n'
    r'            \}'
)
INSERT_4 = '''            Item {
                Layout.fillWidth: true
                // AccessExplainer: let InlineMessage manage its own height
                // (its docs recommend against setting height on it
                // directly) instead of clipping it to a fixed 32px.
                implicitHeight: message.visible ? message.implicitHeight : 0
                height: implicitHeight

                Kirigami.InlineMessage {
                    id: message
                    anchors.left: parent.left
                    anchors.right: parent.right
                    showCloseButton: true
                }
            }'''


# Anchor 5/6 together wrap loginFrame's content (the loginColumn
# ColumnLayout) in a plain Item holding a background Rectangle behind it.
# Window.qml (package qml-module-lliurex-ui, a different package from
# lliurex-sddm-theme) hardcodes the window's own gray background
# (#eff0f1) with no exposed property to override it, and isn't patched
# by this project (deliberately - see AGENTS.md on why). So this paints
# an inset panel just behind our own content instead: the thin gray
# margin from Window.qml's own background stays visible around it.
#
# Two separate anchors instead of one spanning the whole ColumnLayout
# block, to keep each one small and unambiguous: 5 adds the wrapper's
# opening (Item + Rectangle) right before "ColumnLayout { id: loginColumn
# ...", 6 adds the matching closing brace right after that ColumnLayout's
# own closing brace. loginColumn's own "anchors.fill: parent" still
# works unchanged - its runtime parent is now the wrapper Item instead of
# loginFrame directly, which fills the same space via its own
# anchors.fill: parent.
ANCHOR_5 = '''        ColumnLayout {
            id: loginColumn
            spacing: 8
            anchors.fill: parent
'''
INSERT_5 = '''        Item {
            anchors.fill: parent

            Rectangle {
                anchors.fill: parent
                color: "#c6ebfe"
                radius: 4
            }

'''

ANCHOR_6_RE = re.compile(
    r'                onClicked: \{\n'
    r'                    loginFrame\.enabled = false;\n'
    r'                    login\(\);\n'
    r'                \}\n'
    r'            \}\n'
    r'[ \t]*\n'
    r'        \}\n'
    r'[ \t]*\n'
    r'    \}\n'
    r'\n'
    r'    Timer \{\n'
    r'        id: timerAutoLogin'
)
INSERT_6 = '''                onClicked: {
                    loginFrame.enabled = false;
                    login();
                }
            }

        }
        }

    }

    Timer {
        id: timerAutoLogin'''

# Anchor 7: a small label so testers/IT staff can tell at a glance that
# this pilot machine has the explainer active, instead of silently
# changing login-failure behavior with no visible indicator.
ANCHOR_7_RE = re.compile(
    r'            Rectangle \{\n'
    r'                color: "#7f8c8d"\n'
    r'                height: 5\n'
    r'                width: 320\n'
    r'                Layout\.alignment: Qt\.AlignHCenter\n'
    r'            \}\n'
    r'[ \t]*\n'
    r'            Item \{\n'
    r'                Layout\.fillHeight:true\n'
    r'            \}'
)
INSERT_7 = '''            Rectangle {
                color: "#7f8c8d"
                height: 5
                width: 320
                Layout.alignment: Qt.AlignHCenter
            }

            PlasmaComponents.Label {
                // AccessExplainer: this static label isn't in the
                // theme's own translation catalog, so i18nd() would
                // just echo back whatever string we pass regardless of
                // locale - pick the text ourselves instead, the same
                // way explainerLang() already does for the dynamic
                // AccessExplainer messages. Version comes from the
                // repo's own VERSION file at patch-generation time, not
                // hardcoded here - see PROJECT_VERSION above.
                text: explainerLang() === "ca" ? "Assistent d'accés v__VERSION__" : "Asistente de acceso v__VERSION__"
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.96
                opacity: 0.7
            }

            Item {
                Layout.fillHeight:true
            }'''.replace("__VERSION__", PROJECT_VERSION)


# Anchor 8: enlarge the whole login box ~10% (400x340 -> 440x374), per an
# ad hoc request while testing.
ANCHOR_8 = '''    LLX.Window {
        id: loginFrame
        visible: root.topWindow == this
        width: 400
        height: 340
        margin:24'''
INSERT_8 = '''    LLX.Window {
        id: loginFrame
        visible: root.topWindow == this
        width: 440
        height: 374
        margin:24'''

# Anchors 9/10/11: scale up the font of every text element in the login
# box ~10% relative to the theme's own current default size (not a
# hardcoded absolute size), per the same ad hoc request. Kirigami.Theme
# is already imported at the top of this file as "Kirigami".
ANCHOR_9 = '''                PlasmaComponents.TextField {
                    id: txtUser
                    implicitWidth: 200
                    focus: true
                    placeholderText: i18nd("lliurex-sddm-theme","User name")'''
INSERT_9 = '''                PlasmaComponents.TextField {
                    id: txtUser
                    implicitWidth: 200
                    focus: true
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2
                    placeholderText: i18nd("lliurex-sddm-theme","User name")'''

ANCHOR_10 = '''                PlasmaComponents.TextField {
                    id: txtPass
                    implicitWidth: 200
                    echoMode: TextInput.Password
                    placeholderText: i18nd("lliurex-sddm-theme","Password")'''
INSERT_10 = '''                PlasmaComponents.TextField {
                    id: txtPass
                    implicitWidth: 200
                    echoMode: TextInput.Password
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2
                    placeholderText: i18nd("lliurex-sddm-theme","Password")'''

ANCHOR_11 = '''            PlasmaComponents.Button {
                id: btnLogin
                text: i18nd("lliurex-sddm-theme","Login");
                implicitWidth: 200'''
INSERT_11 = '''            PlasmaComponents.Button {
                id: btnLogin
                text: i18nd("lliurex-sddm-theme","Login");
                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2
                implicitWidth: 200'''


# Anchors 12/13: make showError/showWarning restart the auto-hide timer
# every time they're called, so ANY message shown through them
# (AccessExplainer's or the theme's own WiFi-related ones) auto-hides
# after explainerDisplayMs, not just the ones this project added.
ANCHOR_12 = '''    function showError(msg)
    {
        message.type=Kirigami.MessageType.Error;
        message.text=msg;
        message.visible=true;
        root.topWindow = loginFrame;
        root.topWindow.enabled = true;
    }'''
INSERT_12 = '''    function showError(msg)
    {
        message.type=Kirigami.MessageType.Error;
        message.text=msg;
        message.visible=true;
        root.topWindow = loginFrame;
        root.topWindow.enabled = true;
        messageAutoHideTimer.restart();
    }'''

ANCHOR_13 = '''    function showWarning(msg)
    {
        message.type = Kirigami.MessageType.Warning;
        message.text = msg;
        message.visible = true;
        //root.topWindow = loginFrame;
        root.topWindow.enabled = true;
    }'''
INSERT_13 = '''    function showWarning(msg)
    {
        message.type = Kirigami.MessageType.Warning;
        message.text = msg;
        message.visible = true;
        //root.topWindow = loginFrame;
        root.topWindow.enabled = true;
        messageAutoHideTimer.restart();
    }'''

# Anchor 14: the explainerDisplayMs property and the auto-hide Timer
# itself. Placed right before the existing clock timer, using only its
# first lines as the anchor (its own onTriggered body has several
# blank/whitespace-only lines that aren't worth regex-matching here
# since we only need to insert something *before* this block).
ANCHOR_14 = '''    readonly property int autoLoginTimeout: 30000 //30 seconds'''
INSERT_14 = '''    readonly property int autoLoginTimeout: 30000 //30 seconds

    // AccessExplainer: how long (ms) the login-failure message stays
    // visible before auto-hiding; overwritten once get_display_seconds()
    // responds (see local_get_display_seconds above). This default is
    // only used until then, or if that call fails.
    property int explainerDisplayMs: 20000

    // AccessExplainer: Ethernet/Wi-Fi IPs, filled once
    // local_get_network_info responds; empty until then or if it fails
    // (the status bar label just hides itself in that case).
    property string explainerNetworkInfo: ""'''

ANCHOR_15 = '''    /* Clock refresh timer */
    Timer {
        id: timerClock'''
INSERT_15 = '''    // AccessExplainer: auto-hide the login-failure message after
    // explainerDisplayMs, and immediately whenever the user edits
    // either field (see txtUser/txtPass onTextChanged below).
    Timer {
        id: messageAutoHideTimer
        interval: root.explainerDisplayMs
        repeat: false
        onTriggered: { message.visible = false; }
    }

    /* Clock refresh timer */
    Timer {
        id: timerClock'''

# Anchor 16: trigger the get_display_seconds fetch alongside the other
# startup calls.
ANCHOR_16_RE = re.compile(
    r'        local_get_settings\.call\(\[\]\);\n'
    r'        local_get_autologin\.call\(\[\]\);\n'
    r'        local_get_whitelist\.call\(\[\]\);\n'
    r'        local_lliurex_version\.call\(\[\]\);\n'
    r'[ \t]*\n'
    r'        tags\.reload\(\);'
)
INSERT_16 = '''        local_get_settings.call([]);
        local_get_autologin.call([]);
        local_get_whitelist.call([]);
        local_lliurex_version.call([]);
        local_get_display_seconds.call([]);
        local_get_network_info.call([]);

        tags.reload();'''

# Anchor 17: clear the message as soon as the user edits txtUser - this
# block (onEditingFinished) is untouched by the earlier font-size patch
# (ANCHOR_9), so it's a safe, independent anchor regardless of patch
# order.
ANCHOR_17 = '''                    onEditingFinished: {
                        txtPass.focus=true
                    }'''
INSERT_17 = '''                    onEditingFinished: {
                        txtPass.focus=true
                    }
                    onTextChanged: {
                        // AccessExplainer: clear any shown message as
                        // soon as the user starts correcting their input.
                        message.visible = false;
                        messageAutoHideTimer.stop();
                    }'''

# Anchor 18: same for txtPass. Anchored on text that already includes
# the font.pixelSize line from ANCHOR_10/INSERT_10, since this
# transformation runs after that one on the same working copy.
ANCHOR_18_RE = re.compile(
    r'                    font\.pixelSize: Kirigami\.Theme\.defaultFont\.pixelSize \* 1\.2\n'
    r'                    placeholderText: i18nd\("lliurex-sddm-theme","Password"\)\n'
    r'[ \t]*\n'
    r'                    Keys\.onReturnPressed: \{'
)
INSERT_18 = '''                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2
                    placeholderText: i18nd("lliurex-sddm-theme","Password")
                    onTextChanged: {
                        // AccessExplainer: clear any shown message as
                        // soon as the user starts correcting their input.
                        message.visible = false;
                        messageAutoHideTimer.stop();
                    }

                    Keys.onReturnPressed: {'''

# Anchor 19: a status-bar label showing physical Ethernet/Wi-Fi IPs,
# next to the existing hostname label. Regex-matched because of the
# original's blank-with-whitespace lines inside the block.
ANCHOR_19_RE = re.compile(
    r'            PlasmaComponents\.Label \{\n'
    r'                id: widgetHost\n'
    r'                Layout\.alignment: Qt\.AlignRight\n'
    r'[ \t]*\n'
    r'                horizontalAlignment: Text\.AlignHCenter\n'
    r'[ \t]*\n'
    r'                text: sddm\.hostName\n'
    r'[ \t]*\n'
    r'            \}'
)
INSERT_19 = '''            PlasmaComponents.Label {
                id: widgetHost
                Layout.alignment: Qt.AlignRight

                horizontalAlignment: Text.AlignHCenter

                text: sddm.hostName

            }

            PlasmaComponents.Label {
                // AccessExplainer: physical Ethernet/Wi-Fi IPs only
                // (see get_network_info() in AccessExplainer.py) - makes
                // it easy to identify this machine when helping remotely.
                id: widgetNetworkInfo
                Layout.alignment: Qt.AlignRight

                horizontalAlignment: Text.AlignHCenter

                text: root.explainerNetworkInfo
                visible: text.length > 0
            }'''


def apply_literal_once(text, anchor, insert_before, label):
    count = text.count(anchor)
    if count != 1:
        sys.exit(f"ERROR: anchor '{label}' found {count} times (expected exactly 1). "
                  f"Theme source likely changed - review manually before patching.")
    return text.replace(anchor, insert_before + anchor, 1)


def apply_replacement_once(text, anchor, replacement, label):
    '''Like apply_literal_once, but replaces the matched anchor text
    outright instead of inserting something before it.'''
    count = text.count(anchor)
    if count != 1:
        sys.exit(f"ERROR: anchor '{label}' found {count} times (expected exactly 1). "
                  f"Theme source likely changed - review manually before patching.")
    return text.replace(anchor, replacement, 1)


def apply_regex_once(text, pattern, replacement, label):
    matches = pattern.findall(text)
    if len(matches) != 1:
        sys.exit(f"ERROR: anchor '{label}' matched {len(matches)} times (expected exactly 1). "
                  f"Theme source likely changed - review manually before patching.")
    return pattern.sub(lambda m: replacement, text, count=1)


def main():
    text = SRC.read_text(encoding="utf-8")
    original = text

    text = apply_literal_once(text, ANCHOR_1, INSERT_1, "showWarning (add explainerLang)")
    text = apply_literal_once(text, ANCHOR_2, INSERT_2, "local_get_active_connections (add N4D.Proxy)")
    text = apply_regex_once(text, ANCHOR_3_RE, INSERT_3, "onLoginFailed (call AccessExplainer)")
    text = apply_regex_once(text, ANCHOR_4_RE, INSERT_4, "message box (let InlineMessage size itself)")
    text = apply_literal_once(text, ANCHOR_5, INSERT_5, "loginColumn wrapper open (background panel)")
    text = apply_regex_once(text, ANCHOR_6_RE, INSERT_6, "loginColumn wrapper close (background panel)")
    text = apply_regex_once(text, ANCHOR_7_RE, INSERT_7, "pilot-active label")
    text = apply_replacement_once(text, ANCHOR_8, INSERT_8, "login box size +10%")
    text = apply_replacement_once(text, ANCHOR_9, INSERT_9, "txtUser font +10%")
    text = apply_replacement_once(text, ANCHOR_10, INSERT_10, "txtPass font +10%")
    text = apply_replacement_once(text, ANCHOR_11, INSERT_11, "btnLogin font +10%")
    text = apply_replacement_once(text, ANCHOR_12, INSERT_12, "showError (restart auto-hide timer)")
    text = apply_replacement_once(text, ANCHOR_13, INSERT_13, "showWarning (restart auto-hide timer)")
    text = apply_replacement_once(text, ANCHOR_14, INSERT_14, "explainerDisplayMs property")
    text = apply_replacement_once(text, ANCHOR_15, INSERT_15, "messageAutoHideTimer")
    text = apply_regex_once(text, ANCHOR_16_RE, INSERT_16, "fetch get_display_seconds on startup")
    text = apply_replacement_once(text, ANCHOR_17, INSERT_17, "txtUser onTextChanged clears message")
    text = apply_regex_once(text, ANCHOR_18_RE, INSERT_18, "txtPass onTextChanged clears message")
    text = apply_regex_once(text, ANCHOR_19_RE, INSERT_19, "widgetNetworkInfo status bar label")

    if text == original:
        sys.exit("ERROR: no changes were applied, refusing to write an unpatched file")

    DST.write_text(text, encoding="utf-8")
    print(f"Wrote {DST} ({len(text.splitlines())} lines)")
    print("sha256 pristine:", hashlib.sha256(original.encode()).hexdigest())
    print("sha256 patched :", hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    main()
