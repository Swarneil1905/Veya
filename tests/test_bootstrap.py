"""Exercise the actual PowerShell bootstrap with deterministic dependency failures."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    shutil.which("pwsh") or shutil.which("powershell"), "PowerShell required"
)
class BootstrapTest(unittest.TestCase):
    def test_dependency_failure_stops_without_false_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            shutil.copyfile(ROOT / "scripts/dev.ps1", root / "scripts/dev.ps1")
            (root / ".python-version").write_text("3.13.14")
            wrapper = root / "exercise.ps1"
            wrapper.write_text("""
$ErrorActionPreference='Stop'
function python { $global:LASTEXITCODE=0 }
function node { $global:LASTEXITCODE=0 }
function pnpm { Write-Output 'SIMULATED_DEPENDENCY_FAILURE'; $global:LASTEXITCODE=7 }
function uv { throw 'SHOULD_NOT_REACH_UV' }
function cargo { throw 'SHOULD_NOT_REACH_CARGO' }
function rustc { $global:LASTEXITCODE=0 }
& (Join-Path $PSScriptRoot 'scripts/dev.ps1')
""")
            result = subprocess.run(
                [
                    shutil.which("pwsh") or shutil.which("powershell"),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(wrapper),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            text = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, text)
            self.assertIn("Dependency step failed (7)", text)
            self.assertNotIn("Veya is ready", text)
            self.assertNotIn("SHOULD_NOT_REACH", text)
