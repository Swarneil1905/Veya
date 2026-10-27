"""Run runtime tests with the selected Python interpreter and an isolated temp root."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
artifacts = root / 'artifacts'
artifacts.mkdir(exist_ok=True)
environment = os.environ.copy()
environment['PYTHONPATH'] = str(root / 'services/runtime')
with tempfile.TemporaryDirectory(prefix='runtime-tests-', dir=artifacts) as temporary:
    arguments = sys.argv[1:] or ['services/runtime/tests']
    # The cross-platform suite now exceeds 500 cases; allow slow Windows CI disks
    # while retaining a hard bound below the workflow job timeout.
    result = subprocess.run([sys.executable, '-m', 'pytest', *arguments, '--basetemp', temporary],
                            cwd=root, env=environment, check=False, timeout=300)
    sys.exit(result.returncode)
