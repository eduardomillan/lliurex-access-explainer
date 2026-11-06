# Kirigami

Notes on the QML framework behind several pieces of this project's
`Main.qml` patch (`Kirigami.InlineMessage`, `Kirigami.Theme`,
`Kirigami.MessageType`), written down because getting its conventions
wrong already caused one real, hard-to-spot bug here (see
[RISKS.md](RISKS.md) and `AGENTS.md`).

## What it is

Kirigami is KDE's QML component framework for building Plasma/Qt Quick
applications - things like dialogs, pages, headers, and the
`InlineMessage` control this project's login screen already used before
this project touched it. It sits on top of Qt Quick Controls 2 and
follows KDE's Human Interface Guidelines. `lliurex-sddm-theme` imports it
as `import org.kde.kirigami 2.16 as Kirigami` at the top of `Main.qml`.

It is not a general-purpose UI toolkit for everything - it's specifically
the KDE/Plasma ecosystem's component library, which is why it's already
present on every LliureX client (KDE Plasma desktop) and why
`lliurex-sddm-theme` builds its login screen out of it instead of plain
Qt Quick Controls.

## Components this project touches

### `Kirigami.InlineMessage`

A banner-style message box with a type (info/positive/warning/error), an
optional close button, and optional actions. `Main.qml` already had one
(`id: message`) before this project, used for WiFi-related errors; this
project's patch reuses it to show `AccessExplainer`'s login-failure
explanation instead of adding a new UI element.

**The property that caused a real bug here**: `InlineMessage`'s own
documentation says to avoid setting its `height` directly and let it
manage its own `implicitHeight` - it's designed to size itself to its
(possibly multi-line, possibly animated) content. The original
`lliurex-sddm-theme` code ignored that and wrapped it in a fixed
`height: 32` container with `anchors.fill: parent`, which was fine for
short strings like `"Login failed"` but clipped this project's longer
1-2 sentence messages to only their tail end. The fix: size the wrapping
`Item`'s height from `message.implicitHeight` instead of a fixed number,
and anchor `InlineMessage` to `left`/`right` only, not a height-forcing
`anchors.fill`. See the `ANCHOR_4`/`INSERT_4` patch in
`sddm-theme-patch/apply_patch.py`.

### `Kirigami.MessageType`

An enum (`Kirigami.MessageType.Information`, `.Positive`, `.Warning`,
`.Error`) used to set an `InlineMessage`'s visual style. `Main.qml`'s
existing `showError()`/`showWarning()` helpers just set `message.type` to
one of these values plus the text - this project calls those same
existing helpers rather than reimplementing message display.

### `Kirigami.Theme`

A globally accessible singleton exposing the current Plasma color scheme
and font as QML properties - `Kirigami.Theme.defaultFont`,
`Kirigami.Theme.textColor`, `Kirigami.Theme.highlightColor`, and so on.
Reading from it instead of hardcoding values is how a component stays
consistent with whatever color scheme or font size the user/system has
configured.

**The property that caused a second real bug here**: `Kirigami.Theme.
defaultFont` is a regular `QFont`, and `QFont` has two different size
properties that are easy to confuse:

- `pointSize` - the font size in points, **or `-1` if the font was
  actually defined by pixel size instead** (Qt's convention for "this
  axis wasn't the one used to set it", not an error).
- `pixelSize` - the font size in pixels, **always resolved to a valid
  positive number** regardless of which way the font was originally
  defined, because Qt computes one from the other using the display's
  DPI when needed.

This project first scaled fonts with
`font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.2`. It had
*no visible effect at all* on the real test machine, with no error or
warning anywhere - because that theme's default font is defined by pixel
size, so `defaultFont.pointSize` was `-1`, and `-1 * 1.2 = -1.2` is just
silently treated as "unset, use the default" by Qt Quick. The fix was to
scale `pixelSize` instead:
`font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2`, which works
regardless of how the base theme happened to define its font. See the
`ANCHOR_9`/`ANCHOR_10`/`ANCHOR_11` (and the label's own font line in
`ANCHOR_7`) patches in `sddm-theme-patch/apply_patch.py`.

**Lesson for any future font-related patch here**: never assume
`pointSize` is populated just because a font clearly has *some* visible
size - check (or just default to scaling `pixelSize`) instead of trusting
`pointSize` to be non-negative.

## Where to actually look things up

This file is a narrow, project-specific note, not a Kirigami reference.
For anything not covered above:
- Kirigami's own QML sources are on disk on any KDE Plasma machine,
  including every LliureX client: `/usr/lib/x86_64-linux-gnu/qt5/qml/org/kde/kirigami.2/`
  (and `.../templates/` for the base, less-styled versions of each
  component, like `templates/InlineMessage.qml`, which is where the
  "avoid setting height directly" documentation actually lives).
- KDE's own developer documentation: <https://develop.kde.org/docs/getting-started/kirigami/>
- Qt's `QFont` documentation (for the `pointSize`/`pixelSize` distinction
  specifically): <https://doc.qt.io/qt-5/qfont.html>
