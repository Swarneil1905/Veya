import unittest
from packages.contracts.generate import ts_type, breaking


class ContractGenerationTest(unittest.TestCase):
    def test_required_nullable_nested_array_and_enum(self):
        self.assertEqual(
            ts_type(
                {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "result": {
                            "anyOf": [
                                {"type": "array", "items": {"enum": ["yes", "no"]}},
                                {"type": "null"},
                            ]
                        },
                    },
                }
            ),
            '{ "id": string; "result"?: Array<"yes" | "no"> | null }',
        )
        with self.assertRaises(ValueError):
            ts_type({"type": "unsupported"})

    def test_existing_field_change_requires_contract_version(self):
        before = {"components": {"schemas": {"Task": {"type": "string"}}}, "paths": {}}
        after = {"components": {"schemas": {"Task": {"type": "number"}}}, "paths": {}}
        self.assertTrue(breaking(before, after))
        self.assertFalse(breaking(before, before))
