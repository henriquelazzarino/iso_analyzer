"""Tests for duplication detector and scorer."""
import tempfile
import unittest
from pathlib import Path

from audit.models import AuditReport, ComplexityResult, CouplingResult, CoverageResult
from audit.reporting import scorer
from audit.static_analysis import duplication


DUP_BLOCK = """\
int total = 0;
for (int i = 0; i < items.size(); i++) {
    total += items.get(i).value();
}
return total;
"""


class DuplicationTests(unittest.TestCase):
    def test_detects_cross_file_dup(self):
        with tempfile.TemporaryDirectory() as tmp:
            f1 = Path(tmp) / "A.java"
            f2 = Path(tmp) / "B.java"
            wrapper = "class X { void m() {\n" + DUP_BLOCK + "} }\n"
            f1.write_text(wrapper, encoding="utf-8")
            f2.write_text(wrapper, encoding="utf-8")
            res = duplication.analyze([f1, f2])
            self.assertGreater(res.duplicated_blocks, 0)
            self.assertGreater(res.duplicated_lines, 0)

    def test_no_dup_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            f1 = Path(tmp) / "A.java"
            f1.write_text("class X {}\n", encoding="utf-8")
            res = duplication.analyze([f1])
            self.assertEqual(res.duplicated_blocks, 0)


class ScorerTests(unittest.TestCase):
    def test_failed_when_no_tests(self):
        r = AuditReport()
        r.complexity = ComplexityResult(average=25, total=100)
        r.coupling = CouplingResult(average=25)
        r.coverage = CoverageResult(detected_framework="none")
        score = scorer.score(r)
        self.assertEqual(score.status, "NÃO CONFORME")
        self.assertLess(score.overall, 60)

    def test_approved_when_clean(self):
        r = AuditReport()
        r.complexity = ComplexityResult(average=3)
        r.coupling = CouplingResult(average=3)
        r.coverage = CoverageResult(detected_framework="junit",
                                    executed=True, success=True,
                                    line_coverage=85, branch_coverage=75)
        score = scorer.score(r)
        self.assertIn(score.status, ("CONFORME", "CONFORME COM RESSALVAS"))


if __name__ == "__main__":
    unittest.main()
