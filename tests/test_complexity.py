"""Tests for the cyclomatic complexity calculator."""
import unittest

from audit.models import MethodInfo, ClassInfo
from audit.static_analysis import complexity


def make_method(body: str, name: str = "m") -> MethodInfo:
    return MethodInfo(name=name, start_line=1, end_line=1, body=body)


class ComplexityTests(unittest.TestCase):
    def test_base_complexity_is_one(self):
        m = make_method("return 1;")
        self.assertEqual(complexity.compute_method_complexity(m), 1)

    def test_single_if_adds_one(self):
        m = make_method("if (x > 0) { return x; }")
        self.assertEqual(complexity.compute_method_complexity(m), 2)

    def test_if_else_adds_one(self):
        m = make_method("if (x > 0) { return x; } else { return 0; }")
        self.assertEqual(complexity.compute_method_complexity(m), 2)

    def test_if_elseif_else_adds_two(self):
        body = "if (a) { } else if (b) { } else { }"
        m = make_method(body)
        # Per spec example: if/else if/else => +2  => total 3 (base 1 + 2)
        self.assertEqual(complexity.compute_method_complexity(m), 3)

    def test_chain_of_elseifs(self):
        body = "if (a) {} else if (b) {} else if (c) {} else {}"
        m = make_method(body)
        # base(1) + 1 (if) + 1 (else if b) + 1 (else if c) = 4
        self.assertEqual(complexity.compute_method_complexity(m), 4)

    def test_aggregate(self):
        c1 = ClassInfo(name="A", file_path="A.java", methods=[
            make_method("if (a) {}", "m1"),
            make_method("if (a) {} else if (b) {}", "m2"),
        ])
        result = complexity.analyze([c1])
        self.assertEqual(result.total, 2 + 3)
        self.assertGreaterEqual(len(result.by_method), 2)
        # Top method should be m2 (cc=3)
        self.assertEqual(result.by_method[0]["method"], "m2")


if __name__ == "__main__":
    unittest.main()
