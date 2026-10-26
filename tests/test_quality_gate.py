import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('quality_gate',Path(__file__).parents[1]/'scripts/quality_gate.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
class GateTests(unittest.TestCase):
    def test_only_all_success_is_green(self):
        needs={name:{'result':'success'} for name in gate.REQUIRED}
        self.assertTrue(gate.verify(needs))
        for name in gate.REQUIRED:
            for state in ['failure','cancelled','skipped','neutral',None]:
                self.assertFalse(gate.verify({**needs,name:{'result':state}}))
            self.assertFalse(gate.verify({k:v for k,v in needs.items() if k!=name}))
        self.assertFalse(gate.verify(None))
        self.assertFalse(gate.verify({**needs,'unknown':{'result':'success'}}))
