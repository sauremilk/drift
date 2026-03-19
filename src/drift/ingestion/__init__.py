"""Ingestion layer for Drift — file discovery, AST parsing, git history."""

from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.ingestion.git_history import build_file_histories, parse_git_history

__all__ = [
    "discover_files",
    "parse_file",
    "parse_git_history",
    "build_file_histories",
]
