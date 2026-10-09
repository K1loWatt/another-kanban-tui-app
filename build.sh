#!/usr/bin/env bash
# Build a dev deliverable for kanban-tui: a wheel/sdist via Poetry, plus a
# standalone single-file binary (via PyInstaller) that can be copied to
# another machine without needing Python/Poetry installed there.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "==> Checking for Poetry"
if ! command -v poetry >/dev/null 2>&1; then
    echo "Poetry is not installed. See https://python-poetry.org/docs/#installation" >&2
    exit 1
fi

echo "==> Installing dependencies (including dev tools)"
poetry install --with dev

echo "==> Building wheel + sdist"
poetry build

DIST_DIR="dist"
mkdir -p "$DIST_DIR"

echo "==> Building standalone dev binary with PyInstaller"
if poetry run python -c "import PyInstaller" >/dev/null 2>&1; then
    poetry run pyinstaller \
        --name kanban-tui-dev \
        --onefile \
        --noconfirm \
        --clean \
        --paths "$(pwd)/src" \
        --add-data "$(pwd)/src/kanban_tui/kanban.tcss:kanban_tui" \
        --distpath "$DIST_DIR" \
        --workpath build \
        --specpath build \
        scripts/run_kanban_tui.py

    echo "==> Standalone binary created at $DIST_DIR/kanban-tui-dev"
else
    echo "PyInstaller not available, skipping standalone binary build."
fi

echo
echo "==> Build artifacts in $DIST_DIR:"
ls -la "$DIST_DIR"

echo
echo "Install the wheel elsewhere with:"
echo "  pip install $DIST_DIR/kanban_tui-*.whl"
echo "Or copy and run the standalone dev binary directly:"
echo "  $DIST_DIR/kanban-tui-dev"
