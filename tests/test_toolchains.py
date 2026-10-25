import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ToolchainTests(unittest.TestCase):
    def test_old_and_unsupported_versions_fail_before_installation(self):
        spec=importlib.util.spec_from_file_location('toolchains',ROOT/'scripts/check_toolchains.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for tool,version in [('node','v20.19.0'),('node','v22.12.0'),('node','v23.0.0'),('python','Python 3.9.20'),('python','Python 3.14.0')]:
            with self.subTest(tool=tool,version=version),self.assertRaisesRegex(ValueError,tool):
                module.validate_version(tool,version)
        module.validate_version('python','Python 3.10.11')
        module.validate_version('node','v22.23.2')

    def test_declared_pins_match_installation_files(self):
        spec=importlib.util.spec_from_file_location('toolchains',ROOT/'scripts/check_toolchains.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.check_pins(ROOT)
