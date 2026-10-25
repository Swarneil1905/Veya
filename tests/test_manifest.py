import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('manifest',ROOT/'scripts/verify_manifest.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ManifestTests(unittest.TestCase):
    def test_downloaded_payload_and_commit_must_match(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as tmp:
            root=Path(tmp);(root/'artifacts').mkdir();(root/'payload').write_bytes(b'build')
            manifest={'commit':'expected','native':False,'signed':False,'files':1}
            (root/'artifacts/build-manifest.json').write_text(json.dumps(manifest))
            (root/'artifacts/SHA256SUMS.txt').write_text(hashlib.sha256(b'build').hexdigest()+'  payload\n')
            self.assertEqual(module.verify(root,'expected'),1)
            with self.assertRaises(ValueError): module.verify(root,'other')
            (root/'payload').write_bytes(b'changed')
            with self.assertRaises(ValueError): module.verify(root,'expected')
