"""End-to-end integration: run the orchestrator against the bundled demo project.

This test does NOT require Maven, Gradle, Java runtime, or network access.
It exercises the full static-analysis pipeline plus report generation.
"""
import json
import tempfile
import unittest
from pathlib import Path

from audit.core import AuditOptions, run, setup_logger


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo-java"


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_logger(verbose=False)

    def test_full_audit_on_demo(self):
        self.assertTrue(DEMO.exists(), "Demo project missing")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            opts = AuditOptions(
                source=str(DEMO),
                output_dir=out_dir,
                skip_dynamic=True,
                skip_tests=True,
            )
            report = run(opts)

            # Structural assertions
            self.assertEqual(report.project, "demo-java")
            self.assertGreaterEqual(report.classes_analyzed, 4)
            self.assertGreaterEqual(report.methods_analyzed, 5)
            self.assertIn(report.score.status,
                          ("CONFORME", "CONFORME COM RESSALVAS", "NÃO CONFORME"))

            # Files produced
            self.assertTrue((out_dir / "metrics.json").exists())
            self.assertTrue((out_dir / "report.html").exists())
            data = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
            self.assertIn("score", data)
            self.assertIn("complexity", data)


if __name__ == "__main__":
    unittest.main()
