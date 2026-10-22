import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workspace', ROOT / 'scripts/check_workspace.py')
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class WorkspaceTests(unittest.TestCase):
    def test_repository_has_required_packages(self):
        workspace.check(ROOT)

    def test_missing_runtime_names_the_prerequisite(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            (root / 'apps/desktop').mkdir(parents=True)
            (root / 'apps/desktop/package.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Python sidecar package'):
                workspace.check(root)
