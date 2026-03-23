"""Run pytest and write results to file."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=long", "--no-header"],
    cwd=r"c:\Users\mickg\PWBS\drift",
    capture_output=True,
    text=True,
)

output = result.stdout + result.stderr
with open(r"c:\Users\mickg\PWBS\drift\pytest_results.txt", "w", encoding="utf-8") as f:
    f.write(output)

print("Exit code:", result.returncode)
print("Last 20 lines:")
lines = output.splitlines()
for line in lines[-20:]:
    print(line)
