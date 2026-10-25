import json
import unittest
from packages.fixtures.builders import FixtureBuilder


class BuildersTest(unittest.TestCase):
    def test_same_seed_is_byte_stable_and_order_independent(self):
        a, b = FixtureBuilder("demo"), FixtureBuilder("demo")
        first = a.task("invoice")
        b.user("unrelated")
        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(b.task("invoice"), sort_keys=True),
        )
        self.assertNotEqual(first["id"], FixtureBuilder("other").task("invoice")["id"])
        self.assertEqual(first["created_at"], "2026-01-01T00:00:00+00:00")

    def test_records_have_fixture_identity_and_document_provenance(self):
        f = FixtureBuilder("demo")
        for value in (f.tenant(), f.user("alice"), f.task("task"), f.document("order")):
            self.assertTrue(value["id"].startswith("fixture_"))
            self.assertTrue(value["synthetic"])
        self.assertEqual(f.document("order")["tenant_id"], f.tenant()["id"])
        with self.assertRaises(ValueError):
            FixtureBuilder("")
