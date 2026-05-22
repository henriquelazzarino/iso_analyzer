"""Tests for CBO coupling metric."""
import unittest

from audit.models import ClassInfo
from audit.static_analysis import coupling


class CouplingTests(unittest.TestCase):
    def test_simple_cbo(self):
        a = ClassInfo(
            name="A", file_path="A.java", package="x",
            imports=["com.foo.Bar", "com.foo.Baz", "java.lang.String"],
            referenced_types=["Bar", "Baz", "Logger"],
        )
        result = coupling.analyze([a])
        row = result.by_class[0]
        self.assertEqual(row["class"], "A")
        # Bar, Baz, Logger — java.lang.String filtered
        self.assertEqual(row["cbo"], 3)
        self.assertEqual(result.classification, "Bom")

    def test_self_ref_excluded(self):
        a = ClassInfo(
            name="A", file_path="A.java",
            imports=["com.foo.A"],   # self in different package
            referenced_types=["A", "B"],
        )
        result = coupling.analyze([a])
        # A is filtered; only B remains
        self.assertEqual(result.by_class[0]["cbo"], 1)

    def test_critical_flag(self):
        deps = [f"Dep{i}" for i in range(25)]
        a = ClassInfo(name="Big", file_path="B.java", referenced_types=deps)
        result = coupling.analyze([a])
        self.assertEqual(result.classification, "Crítico")
        self.assertIn("Big", result.critical_classes)


if __name__ == "__main__":
    unittest.main()
