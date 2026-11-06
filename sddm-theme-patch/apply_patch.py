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


def apply_literal_once(text, anchor, insert_before, label):
    count = text.count(anchor)
    if count != 1:
        sys.exit(f"ERROR: anchor '{label}' found {count} times (expected exactly 1). "
                  f"Theme source likely changed - review manually before patching.")
    return text.replace(anchor, insert_before + anchor, 1)


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

    if text == original:
        sys.exit("ERROR: no changes were applied, refusing to write an unpatched file")

    DST.write_text(text, encoding="utf-8")
    print(f"Wrote {DST} ({len(text.splitlines())} lines)")
    print("sha256 pristine:", hashlib.sha256(original.encode()).hexdigest())
    print("sha256 patched :", hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    main()
