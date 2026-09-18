#!/usr/bin/env bash
#
# Build the portable macOS bundle for Planner.
#
# Produces Planner.app carrying its own Python and every dependency, so the Mac
# it lands on needs no Python, uv or git - download, unzip, double-click. The
# app opens in your default browser and quits once the last tab closes.
#
# The bundle is built for the architecture of the machine running this script.
#
# Usage:
#   ./scripts/make_dist.sh [--version 1.0.0] [--no-zip] [--xz]

set -euo pipefail

VERSION="1.0.0"
MAKE_ZIP=1
MAKE_XZ=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --version=*) VERSION="${1#*=}"; shift ;;
        --no-zip) MAKE_ZIP=0; shift ;;
        --xz) MAKE_XZ=1; shift ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

PY_VERSION=3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P_LIB=""   # set once the interpreter is in place
cd "$ROOT"

case "$(uname -m)" in
    arm64)  PY_ARCH="aarch64" ;;
    x86_64) PY_ARCH="x86_64" ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

APP="$ROOT/dist/Planner.app"
RESOURCES="$APP/Contents/Resources"
BUILD="$ROOT/build"

step() { echo ""; echo "==> $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

command -v uv >/dev/null || die "uv not found: https://docs.astral.sh/uv/"

echo "Building Planner $VERSION for macOS ($(uname -m))"

step "[1/7] Skeleton"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$RESOURCES/bin" "$BUILD"

step "[2/7] Bundling Python $PY_VERSION"
# A uv-managed (python-build-standalone) interpreter is relocatable. A `uv venv`
# would not do: it only symlinks back to the Python that made it.
uv python install "$PY_VERSION" >/dev/null 2>&1 || true
PATTERN="cpython-$PY_VERSION.*-macos-$PY_ARCH-none"
SRC="$(ls -d "$(uv python dir)"/$PATTERN 2>/dev/null | sort -V | tail -1)"
[[ -n "$SRC" && -d "$SRC" ]] \
    || die "no CPython $PY_VERSION for $PY_ARCH; run: uv python install $PY_VERSION"
echo "    $(basename "$SRC")"
cp -R "$SRC" "$RESOURCES/bin/python"
# Installing into the copy is the whole point of having made one.
find "$RESOURCES/bin/python" -name EXTERNALLY-MANAGED -delete
BUNDLED_PY="$RESOURCES/bin/python/bin/python3"
P_LIB="$RESOURCES/bin/python/lib/python$PY_VERSION"

step "[3/7] Installing dependencies"
uv export --no-dev --no-emit-project -o "$BUILD/requirements.txt" >/dev/null
uv pip install --python "$BUNDLED_PY" -r "$BUILD/requirements.txt" --quiet
echo "    $(grep -cE '^[a-zA-Z0-9_.-]+==' "$BUILD/requirements.txt") pinned packages"

step "[4/7] Copying the app"
cp streamlit_app.py bootstrap.py db.py daycard.py palette.py worktime.py "$RESOURCES/"
cp -R app_pages "$RESOURCES/app_pages"
cp -R .streamlit "$RESOURCES/.streamlit"
cp README.md "$RESOURCES/README.md"
find "$RESOURCES" -name '__pycache__' -type d -prune -exec rm -rf {} +
# printf, not echo: bash's echo leaves a literal \n and the TOML is then invalid.
printf '\n[client]\ntoolbarMode = "viewer"\n' >> "$RESOURCES/.streamlit/config.toml"

step "[5/7] Trimming"
# What a packaged Streamlit app never touches. What is absent here is equally
# deliberate: pyarrow's other libraries are linked by pyarrow.lib itself, and
# pydeck/nbextension/__init__.py is imported by pydeck - only its static/ can go.
SITE="$P_LIB/site-packages"
before_trim=$(du -sm "$APP" | cut -f1)
rm -rf "$RESOURCES/bin/python/share/jupyter" "$SITE/pydeck/nbextension/static"
find "$SITE" -type d \( -name tests -o -name testing \) -prune \
     -exec rm -rf {} + 2>/dev/null || true
rm -rf "$SITE/pip" "$SITE"/pip-*.dist-info "$P_LIB/ensurepip" "$P_LIB/idlelib"
rm -rf "$P_LIB/tkinter" "$P_LIB"/lib-dynload/_tkinter*.so
rm -rf "$SITE/pyarrow/include" "$RESOURCES/bin/python/include"
rm -f "$SITE/pyarrow"/libarrow_flight.*.dylib "$SITE/pyarrow"/_flight*.so
# Debug symbols are a third of what is left in the binaries.
find "$RESOURCES/bin/python" \( -name "*.so" -o -name "*.dylib" \) \
     -exec strip -x -S {} + 2>/dev/null || true
echo "    $before_trim MB -> $(du -sm "$APP" | cut -f1) MB"

step "[6/7] Launcher and metadata"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Planner</string>
    <key>CFBundleDisplayName</key><string>Planner</string>
    <key>CFBundleIdentifier</key><string>local.planner</string>
    <key>CFBundleVersion</key><string>$VERSION</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>Planner</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/Planner" <<'LAUNCH'
#!/bin/bash
# Everything is found relative to this script: a bundle can be anywhere, and
# double-clicked it starts in "/".
RESOURCES="$(cd "$(dirname "$0")/../Resources" && pwd)"
PYTHON="$RESOURCES/bin/python/bin/python3"

if [ ! -x "$PYTHON" ]; then
    # No console here, so a message has to be shown rather than printed. The
    # usual cause is running it from inside the zip without unpacking first.
    osascript -e 'display dialog "Planner is missing its Python. Unzip the app \
before opening it." with title "Planner" buttons {"OK"} with icon stop' \
        >/dev/null 2>&1
    exit 1
fi
exec "$PYTHON" "$RESOURCES/bootstrap.py"
LAUNCH
chmod +x "$APP/Contents/MacOS/Planner"

# Signing comes last: stripping removes a signature, and arm64 macOS kills
# unsigned code on load. Each binary needs its own, not just the bundle.
find "$RESOURCES/bin/python" \( -name "*.so" -o -name "*.dylib" \) \
     -exec codesign --force --sign - {} + 2>/dev/null || true
codesign --force --sign - "$BUNDLED_PY" >/dev/null 2>&1 || true
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

step "[7/7] Packaging"
SIZE="$(du -sh "$APP" | cut -f1)"
echo "    $APP ($SIZE)"
# No version in the archive names: that keeps the GitHub
# releases/latest/download/<name> link permanent. The version is in Info.plist.
if [[ $MAKE_ZIP == 1 ]]; then
    ZIP="$ROOT/dist/Planner-macos-$(uname -m).zip"
    rm -f "$ZIP"
    ( cd "$ROOT/dist" && ditto -c -k --keepParent "Planner.app" "$ZIP" )
    echo "    $ZIP ($(du -sh "$ZIP" | cut -f1))"
fi
if [[ $MAKE_XZ == 1 ]]; then
    # Roughly half the zip, at the cost of needing tar to open it.
    XZ="$ROOT/dist/Planner-macos-$(uname -m).tar.xz"
    rm -f "$XZ"
    ( cd "$ROOT/dist" && tar -cJf "$XZ" "Planner.app" )
    echo "    $XZ ($(du -sh "$XZ" | cut -f1))"
fi
echo ""
echo "Done."
