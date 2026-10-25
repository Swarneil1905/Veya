import tempfile
import unittest
from pathlib import Path
from scripts.check_boundaries import check


class BoundariesTest(unittest.TestCase):
    def test_inward_dependency_and_storage_import_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            domain = root / "services/runtime/veya/domain/models.py"
            domain.parent.mkdir(parents=True)
            domain.write_text(
                "from dataclasses import dataclass\nfrom veya.domain.lifecycle import transition\n"
            )
            self.assertEqual(check(root), [])
            domain.write_text("from veya.storage.sqlite import Database\n")
            self.assertIn("domain", check(root)[0])

    def test_ui_secret_and_dynamic_import_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui = root / "apps/desktop/src/example.ts"
            ui.parent.mkdir(parents=True)
            for source in [
                "import secret from '../../../../services/runtime/vault';",
                "const x = import('node:fs');",
                "const x = import(moduleName);",
            ]:
                ui.write_text(source)
                self.assertTrue(check(root), source)
            ui.write_text("import {Component} from '@angular/core';")
            self.assertEqual(check(root), [])
