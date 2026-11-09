#!/usr/bin/env bash
# Build the .deb package and publish it as a GitHub Release asset.
#
# Usage: scripts/build-release.sh [--no-publish]
#   --no-publish: build the .deb into dist/ but skip creating the git
#                 tag, the GitHub Release, and the asset upload.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PUBLISH=1
if [[ "${1:-}" == "--no-publish" ]]; then
    PUBLISH=0
fi

VERSION="$(cat VERSION)"
TAG="v${VERSION}"
PKG_NAME="lliurex-access-explainer"

echo "==> Building ${PKG_NAME} ${VERSION}"
fakeroot debian/rules clean
dpkg-buildpackage -us -uc -b

DEB_PATH="../${PKG_NAME}_${VERSION}-1_all.deb"
if [[ ! -f "$DEB_PATH" ]]; then
    echo "error: expected ${DEB_PATH} after build, not found" >&2
    exit 1
fi

echo "==> Running lintian (warnings only, won't fail the build)"
lintian "$DEB_PATH" || true

mkdir -p dist
mv -f "../${PKG_NAME}_${VERSION}-1_all.deb" \
      "../${PKG_NAME}_${VERSION}-1_amd64.changes" \
      "../${PKG_NAME}_${VERSION}-1_amd64.buildinfo" \
      dist/
DEB_PATH="dist/${PKG_NAME}_${VERSION}-1_all.deb"
echo "==> .deb ready at ${REPO_ROOT}/${DEB_PATH}"

if [[ "$PUBLISH" -eq 0 ]]; then
    echo "==> --no-publish given, stopping here (no tag, no release)"
    exit 0
fi

echo "==> Tagging ${TAG}"
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "    tag ${TAG} already exists locally, reusing it"
else
    git tag -a "$TAG" -m "Release ${TAG}"
    git push origin "$TAG"
fi

NOTES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE"' EXIT
{
    echo "Pilot build for testers. Not yet validated through a full"
    echo "install/upgrade/remove/purge cycle on every target machine -"
    echo "see docs/ISSUES.md for known open items before relying on this"
    echo "in a real classroom."
    echo
    awk -v ver="[${VERSION}]" '
        $0 ~ "^## \\" ver { found=1; print; next }
        found && /^## \[/ { exit }
        found { print }
    ' CHANGELOG.md
} > "$NOTES_FILE"

echo "==> Creating GitHub release ${TAG}"
if gh release view "$TAG" >/dev/null 2>&1; then
    gh release upload "$TAG" "$DEB_PATH" --clobber
else
    gh release create "$TAG" "$DEB_PATH" \
        --title "${PKG_NAME} ${TAG}" \
        --notes-file "$NOTES_FILE"
fi

echo "==> Done: $(gh release view "$TAG" --json url -q .url)"
