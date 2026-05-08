#!/usr/bin/env bash
set -euo pipefail

REPO_URL="git+https://github.com/rsnemmen/consensus-rank.git"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if ! command -v uv >/dev/null 2>&1; then
  info "uv not found — installing via https://astral.sh/uv"
  curl -fsSL https://astral.sh/uv/install.sh | sh
  # Source the env file Astral's installer drops so this script sees uv
  # shellcheck disable=SC1091
  [ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"
  export PATH="$HOME/.local/bin:${PATH}"
  command -v uv >/dev/null 2>&1 \
    || err "uv installation failed — please install manually: https://astral.sh/uv"
fi

info "Installing consensus-rank"
uv tool install --force "$REPO_URL"

if command -v rank >/dev/null 2>&1; then
  info "Done. Try: rank --help"
else
  warn "'rank' was installed but is not on PATH yet."
  warn "Run: uv tool update-shell"
  warn "Or add ~/.local/bin to your PATH, then open a new terminal."
fi
