"""Diagnose which self-analysis findings are not actionable."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from drift.analyzer import analyze_repo
from drift.config import DriftConfig

ACTION_VERBS = re.compile(
    r"\b("
    r"[Kk]onsolidiere|[Ee]ntferne|[Ff]üge|[Pp]rüfe|"
    r"[Aa]ufteilen|[Ee]rwäge|[Kk]lären|[Ee]rsetze|[Vv]ereinheitliche|"
    r"[Vv]erschiebe|[Aa]nleg[en]|[Ii]mportiere|[Ss]telle\s+sicher|"
    r"[Ee]rstelle|[Hh]inzufügen|[Aa]ktualisiere|[Bb]ehalte|"
    r"[Rr]emove|[Aa]dd|[Ee]xtract|[Cc]onsolidate|[Ss]plit|[Mm]ove|"
    r"[Rr]efactor|[Rr]eplace|[Ii]ntroduce|[Cc]reate|[Dd]elete|"
    r"[Mm]erge|[Ii]nline|[Ww]rap|[Uu]nify|[Cc]ombine"
    r")\b",
    re.UNICODE,
)

SPECIFICITY_PATTERNS = [
    re.compile(r"\d+"),
    re.compile(r"\b[A-Za-z_]\w*\.(py|ts|js|yaml|yml|json|md|toml|cfg)\b"),
    re.compile(r"\b[a-z_]\w*\("),
    re.compile(
        r"\b(Complexity|Commits?|Autoren|Pattern|Docstring|Tests?|"
        r"Return-Type|Import|Abhängigkeit|Service-Schicht|Interface)\b",
        re.UNICODE,
    ),
    re.compile(r"[A-Z][a-z]+[A-Z]"),
    re.compile(r"\b\d+×\b"),
]


def is_actionable(fix: str):
    issues = []
    if not ACTION_VERBS.search(fix):
        issues.append("no action verb")
    if not any(p.search(fix) for p in SPECIFICITY_PATTERNS):
        issues.append("no specific reference")
    return len(issues) == 0, issues


repo_root = Path(__file__).resolve().parent
config = DriftConfig(
    include=["**/*.py"],
    exclude=["**/__pycache__/**", "**/node_modules/**", "**/.venv*/**"],
    embeddings_enabled=False,
)
analysis = analyze_repo(repo_root, config=config, since_days=365)

not_actionable = []
for finding in analysis.findings:
    if not finding.fix:
        continue
    ok, issues = is_actionable(finding.fix)
    if not ok:
        not_actionable.append((finding, issues))

with open(r"c:\Users\mickg\PWBS\drift\diag_out2.txt", "w", encoding="utf-8") as outf:
    outf.write(f"Total findings with fix: {sum(1 for finding in analysis.findings if finding.fix)}\n")
    outf.write(f"Not actionable: {len(not_actionable)}\n\n")
    for finding, issues in not_actionable:
        outf.write(f"[{finding.signal_type.value}] {finding.title}\n")
        outf.write(f"  Issues: {', '.join(issues)}\n")
        outf.write(f"  Fix: {finding.fix!r}\n\n")
