"""JUnit XML output formatter for CI integrations (Jenkins, GitLab, Azure DevOps)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from drift.api_helpers import signal_abbrev
from drift.models import RepoAnalysis


def analysis_to_junit(analysis: RepoAnalysis) -> str:
    """Serialize findings as JUnit XML testsuites for universal CI consumption."""
    testsuites = ET.Element("testsuites")

    testsuite = ET.SubElement(testsuites, "testsuite")
    testsuite.set("name", "drift")
    testsuite.set("timestamp", datetime.now(tz=UTC).isoformat())
    testsuite.set("tests", str(len(analysis.findings) or 1))
    testsuite.set("failures", str(len(analysis.findings)))
    testsuite.set("errors", "0")

    if not analysis.findings:
        # Emit a single passing testcase so the suite is valid
        tc = ET.SubElement(testsuite, "testcase")
        tc.set("classname", "drift")
        tc.set("name", "no-findings")
    else:
        for finding in analysis.findings:
            file_str = finding.file_path.as_posix() if finding.file_path else "unknown"
            line = finding.start_line or 1
            abbrev = signal_abbrev(finding.signal_type)

            tc = ET.SubElement(testsuite, "testcase")
            tc.set("classname", abbrev)
            tc.set("name", f"{file_str}:{line}")

            failure = ET.SubElement(tc, "failure")
            failure.set("message", finding.title)
            failure.set("type", finding.severity.value)
            failure.text = finding.description

    ET.indent(testsuites, space="  ")
    return ET.tostring(testsuites, encoding="unicode", xml_declaration=True)
