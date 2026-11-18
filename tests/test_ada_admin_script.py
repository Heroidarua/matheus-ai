import subprocess
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "ada-executor"
    / "ada-admin"
)


def test_admin_diagnostics_reports_memory_and_root_disk():
    syntax = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr

    result = subprocess.run(
        ["bash", str(SCRIPT), "diagnostics"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    fields = dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line
    )
    assert fields.get("memory"), result.stdout
    assert fields.get("disk_root"), result.stdout
    assert fields["memory"] != "unavailable (/proc/meminfo could not be read)"
    assert fields["disk_root"] != "unavailable (df and Python disk query failed)"
