#!/bin/sh
# Build the Debian package of Tuxdoku with plain dpkg-deb (no debhelper needed).
#
#   packaging/build_deb.sh [OUTPUT_DIR]        (default: ./dist)
#
# Needs: dpkg-deb, gzip, python3 (all present on any Debian/Ubuntu system).
# The build is reproducible: file times come from SOURCE_DATE_EPOCH
# (default: date of the latest debian/changelog entry).
set -eu

# ---- the ONE place to set the maintainer --------------------------------
MAINTAINER="${TUXDOKU_MAINTAINER:-Siposs Attila <sipiatti@gmail.com>}"
# --------------------------------------------------------------------------

HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/.." && pwd)
OUT=$(mkdir -p "${1:-$SRC/dist}" && cd "${1:-$SRC/dist}" && pwd)
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SRC/tuxdoku/__init__.py")
PKG=tuxdoku
DEB="$OUT/${PKG}_${VERSION}_all.deb"

CL_DATE=$(sed -n 's/^ -- .*>  \(.*\)$/\1/p' "$HERE/debian/changelog" | head -n 1)
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(date -d "$CL_DATE" +%s)}
export SOURCE_DATE_EPOCH
STAMP="@$SOURCE_DATE_EPOCH"

ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT INT TERM
umask 022

subst() {
	sed -e "s|@VERSION@|$VERSION|g" -e "s|@MAINTAINER@|$MAINTAINER|g" "$1"
}

# ---- program -------------------------------------------------------------
install -d "$ROOT/usr/share/tuxdoku/tuxdoku"
( cd "$SRC" && find tuxdoku -type f \
	! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' -print ) | sort |
while read -r f; do
	install -D -m 0644 "$SRC/$f" "$ROOT/usr/share/tuxdoku/$f"
done
# Debian policy: games live in /usr/games; /usr/bin/tuxdoku is a convenience symlink
install -D -m 0755 "$HERE/tuxdoku.sh" "$ROOT/usr/games/tuxdoku"
install -d "$ROOT/usr/bin"
ln -s ../games/tuxdoku "$ROOT/usr/bin/tuxdoku"

# ---- desktop integration ---------------------------------------------------
install -D -m 0644 "$SRC/data/tuxdoku.desktop" "$ROOT/usr/share/applications/tuxdoku.desktop"
for d in "$SRC"/data/icons/hicolor/*/apps; do
	size=$(basename "$(dirname "$d")")
	install -D -m 0644 "$d/tuxdoku.png" "$ROOT/usr/share/icons/hicolor/$size/apps/tuxdoku.png"
done
install -D -m 0644 "$SRC/data/icons/tuxdoku.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/tuxdoku.svg"

# ---- docs ------------------------------------------------------------------
DOC="$ROOT/usr/share/doc/$PKG"
install -d "$DOC" "$ROOT/usr/share/man/man6"
OFL=$(sed -e 's/^[[:space:]]*$/./' -e 's/^/ /' "$SRC/tuxdoku/assets/fonts/OFL.txt")
subst "$HERE/debian/copyright" | awk -v ofl="$OFL" '{ if ($0 == "@OFL_TEXT@") print ofl; else print }' > "$DOC/copyright"
subst "$HERE/debian/changelog" | gzip -9n > "$DOC/changelog.gz"
install -m 0644 "$SRC/README.md" "$SRC/CREDITS.md" "$DOC/"
subst "$HERE/tuxdoku.6" | gzip -9n > "$ROOT/usr/share/man/man6/tuxdoku.6.gz"
install -D -m 0644 "$HERE/debian/lintian-overrides" "$ROOT/usr/share/lintian/overrides/$PKG"
chmod 0644 "$DOC/copyright" "$DOC/changelog.gz" "$ROOT/usr/share/man/man6/tuxdoku.6.gz"

# ---- control area ------------------------------------------------------------
install -d -m 0755 "$ROOT/DEBIAN"
SIZE=$(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
subst "$HERE/debian/control.in" | sed "s|@INSTALLED_SIZE@|$SIZE|" > "$ROOT/DEBIAN/control"
install -m 0755 "$HERE/debian/postinst" "$HERE/debian/prerm" "$ROOT/DEBIAN/"
( cd "$ROOT" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$ROOT/DEBIAN/md5sums"
chmod 0644 "$ROOT/DEBIAN/control" "$ROOT/DEBIAN/md5sums"

# normalise permissions and timestamps for a reproducible archive
find "$ROOT" -type d -exec chmod 0755 {} +
find "$ROOT" -exec touch -h -d "$STAMP" {} +

dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$DEB" >/dev/null
echo "$DEB"
