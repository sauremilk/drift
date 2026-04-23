#!/bin/sh
# Install drift-analyzer - works on macOS, Linux, and WSL.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/mick-gsk/drift/main/scripts/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/mick-gsk/drift/main/scripts/install.sh | sh -s -- --version 2.5.1
#
# This script installs drift-analyzer using the best available Python
# package manager (pipx > uv/uvx > pip), creating an isolated environment
# so drift does not interfere with your project dependencies.

set -eu

VERSION=""
QUIET=0

usage() {
  cat <<EOF
Usage: install.sh [OPTIONS]

Options:
  --version VERSION   Install a specific version (e.g. 2.5.1)
  --quiet             Suppress non-error output
  --help              Show this help message
EOF
  exit 0
}

log() {
  if [ "$QUIET" -eq 0 ]; then
    printf '%s\n' "$@"
  fi
}

error() {
  printf 'error: %s\n' "$@" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --quiet)   QUIET=1; shift ;;
    --help)    usage ;;
    *)         error "unknown option: $1" ;;
  esac
done

SPEC="drift-analyzer"
if [ -n "$VERSION" ]; then
  SPEC="drift-analyzer==${VERSION}"
fi

# --- Detect best installer ---
if command -v pipx >/dev/null 2>&1; then
  log "Installing ${SPEC} via pipx..."
  pipx install "$SPEC"
elif command -v uv >/dev/null 2>&1; then
  log "Installing ${SPEC} via uv tool..."
  uv tool install "$SPEC"
elif command -v pip >/dev/null 2>&1; then
  log "Installing ${SPEC} via pip..."
  pip install --user "$SPEC"
elif command -v pip3 >/dev/null 2>&1; then
  log "Installing ${SPEC} via pip3..."
  pip3 install --user "$SPEC"
else
  error "No Python package manager found. Install pipx, uv, or pip first.
  See https://pipx.pypa.io/ or https://docs.astral.sh/uv/"
fi

# --- Verify ---
if command -v drift >/dev/null 2>&1; then
  log ""
  log "drift $(drift --version 2>/dev/null || echo '(installed)')"
  log ""
  log "Get started:"
  log "  drift analyze --repo ."
  log "  drift explain PFS"
  log "  drift --help"
else
  log ""
  log "drift-analyzer was installed but 'drift' is not on your PATH."
  log "You may need to add ~/.local/bin to your PATH:"
  log "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
