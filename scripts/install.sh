#!/usr/bin/env bash
# Install (or update) kanban-tui from the latest GitHub release.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/K1loWatt/another-kanban-tui-app/main/scripts/install.sh | bash
#
# Safe to re-run any time to update to the latest release: it only ever
# downloads a single binary and replaces the one at $INSTALL_DIR/kanban-tui.
# Your tasks and config live elsewhere (~/KanbanTasks and
# ~/.config/kanban-tui/, or wherever KANBAN_TUI_TASKS_DIR points) and are
# never read, written, or deleted by this script.
set -euo pipefail

REPO="K1loWatt/another-kanban-tui-app"
INSTALL_DIR="${KANBAN_TUI_INSTALL_DIR:-$HOME/.local/bin}"
BIN_NAME="kanban-tui"
BIN_PATH="$INSTALL_DIR/$BIN_NAME"

if ! command -v curl >/dev/null 2>&1; then
    echo "Se necesita curl para instalar/actualizar kanban-tui." >&2
    exit 1
fi

os="$(uname -s)"
arch="$(uname -m)"

case "$os-$arch" in
    Linux-x86_64)
        asset="kanban-tui-linux-x86_64"
        ;;
    *)
        echo "No hay binario publicado todavía para $os/$arch." >&2
        echo "Plataformas soportadas de momento: Linux x86_64." >&2
        exit 1
        ;;
esac

previous_version=""
action="Instalando"
if [[ -x "$BIN_PATH" ]]; then
    action="Actualizando"
    previous_version="$("$BIN_PATH" --version 2>/dev/null || true)"
fi

echo "==> Buscando la última release de $REPO"
release_json="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest")"

version="$(printf '%s\n' "$release_json" | grep '"tag_name"' | head -1 | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')"

download_url="$(
    printf '%s\n' "$release_json" \
        | grep -A 40 "\"name\": *\"$asset\"" \
        | grep '"browser_download_url"' \
        | head -1 \
        | sed -E 's/.*"browser_download_url": *"([^"]+)".*/\1/'
)"

if [[ -z "$download_url" ]]; then
    echo "No se encontró el asset '$asset' en la última release (${version:-?})." >&2
    echo "¿Ya se publicó alguna release? (git tag vX.Y.Z && git push origin vX.Y.Z)" >&2
    exit 1
fi

echo "==> $action kanban-tui a $version${previous_version:+ (actual: $previous_version)}"
tmp_bin="$(mktemp)"
trap 'rm -f "$tmp_bin"' EXIT
curl -fsSL "$download_url" -o "$tmp_bin"
chmod +x "$tmp_bin"

mkdir -p "$INSTALL_DIR"
mv "$tmp_bin" "$BIN_PATH"

echo "==> Instalado en $BIN_PATH"

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo
    echo "⚠ $INSTALL_DIR no está en tu PATH todavía. Añade esto a tu ~/.bashrc o ~/.zshrc y abre una terminal nueva:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi

echo
echo "Tus tareas y configuración viven en ~/KanbanTasks y ~/.config/kanban-tui/"
echo "(o donde apunte KANBAN_TUI_TASKS_DIR) — este script nunca las toca, así que"
echo "puedes volver a ejecutarlo cuando quieras para actualizar sin perder nada."
echo

"$BIN_PATH" --version || true
