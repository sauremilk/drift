# Installation

## Quick Install (macOS / Linux / WSL)

```bash
curl -fsSL https://raw.githubusercontent.com/mick-gsk/drift/main/scripts/install.sh | sh
```

This auto-detects the best package manager (pipx > uv > pip) and installs drift in an isolated environment.

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/mick-gsk/drift/main/scripts/install.ps1 | iex
```

## From PyPI

```bash
pip install drift-analyzer
```

## With pipx (recommended for CLI use)

[pipx](https://pipx.pypa.io/) installs drift into an isolated environment so it doesn't interfere with your project dependencies:

```bash
pipx install drift-analyzer
```

Or run without installing using [uvx](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx drift-analyzer analyze --repo .
```

## With Homebrew (macOS / Linux)

```bash
brew tap mick-gsk/drift https://github.com/mick-gsk/drift
brew install drift-analyzer
```

## With Docker

```bash
docker run --rm -v "$(pwd):/src" ghcr.io/mick-gsk/drift:latest analyze --repo /src
```

This mounts your current directory into the container and runs drift against it. No Python installation required.

## With Conda

```bash
# From conda-forge (when available):
conda install -c conda-forge drift-analyzer

# Or build locally from the repo:
conda build conda.recipe/
conda install --use-local drift-analyzer
```

## From Source

```bash
git clone https://github.com/mick-gsk/drift.git
cd drift
pip install -e ".[dev]"
```

## Optional Extras

```bash
# TypeScript/TSX support
pip install -q drift-analyzer[typescript]

# Embedding-based duplicate detection
pip install -q drift-analyzer[embeddings]

# MCP server for IDE integration
pip install -q drift-analyzer[mcp]

# All extras
pip install -q drift-analyzer[all]
```

## Version Pinning

For reproducible CI builds, pin to a specific version:

```bash
# pip
pip install drift-analyzer

# pipx
pipx install drift-analyzer

# GitHub Action
- uses: mick-gsk/drift@v2.9.15

# Docker
docker run ghcr.io/mick-gsk/drift:v2.9.15 analyze --repo /src

# pre-commit
repos:
  - repo: https://github.com/mick-gsk/drift
    rev: v2.9.15
```

## Requirements

- Python 3.11+ (not needed with Docker)
- Git (for history-based signals)

## Editor Integration

Drift integrates with AI coding editors via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/):

```bash
pip install drift-analyzer[mcp]
drift mcp --serve     # start MCP server for IDE integration
```

Setup guides: [Integrations](../integrations.md)

A dedicated VS Code Marketplace extension and JetBrains plugin are planned for a future release.
