"""Review all SMS findings in frappe."""
import json
from pathlib import Path

frappe = json.loads(Path("audit_results/frappe_audit.json").read_text(encoding="utf-8"))
sms_all = [f for f in frappe["findings"] if f["signal"] == "system_misalignment"]
print(f"Total SMS findings: {len(sms_all)}")
for f in sms_all:
    verdict = f.get("verdict", "none")
    desc = (f.get("description") or "")[:250]
    fid = f["id"]
    title = f["title"]
    print(f"  #{fid} [{verdict}]: {title}")
    print(f"    {desc}")
    print()
