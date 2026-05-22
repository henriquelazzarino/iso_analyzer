"""Unit tests for the manual Java parser."""
import os
import tempfile
import unittest
from pathlib import Path

from audit.parsers import parse_java_source, strip_noise


SAMPLE = '''
package com.example.demo;

import java.util.List;
import com.foo.Bar;
import com.foo.Baz;

/** A demo class. */
public class Demo {
    private Bar bar;
    private Baz baz;

    public Demo() {
        this.bar = new Bar();
    }

    public int compute(int x) {
        if (x > 0) {
            return x;
        } else if (x == 0) {
            return 0;
        } else {
            return -x;
        }
    }

    public String greet(String name) {
        // a comment with if () that should not count
        String s = "if (fake)";
        return "hello " + name;
    }
}
'''


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "Demo.java"
        self.path.write_text(SAMPLE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_strip_noise_preserves_line_count(self):
        cleaned = strip_noise(SAMPLE)
        self.assertEqual(cleaned.count("\n"), SAMPLE.count("\n"))
        self.assertNotIn("if (fake)", cleaned)  # string content removed
        self.assertNotIn("a comment", cleaned)  # comment removed

    def test_class_parsed(self):
        classes = parse_java_source(self.path)
        self.assertEqual(len(classes), 1)
        cls = classes[0]
        self.assertEqual(cls.name, "Demo")
        self.assertEqual(cls.package, "com.example.demo")
        self.assertIn("com.foo.Bar", cls.imports)
        method_names = sorted(m.name for m in cls.methods)
        self.assertIn("compute", method_names)
        self.assertIn("greet", method_names)
        self.assertIn("Demo", method_names)  # constructor counted

    def test_referenced_types_exclude_builtins(self):
        classes = parse_java_source(self.path)
        refs = set(classes[0].referenced_types)
        self.assertIn("Bar", refs)
        self.assertIn("Baz", refs)
        self.assertNotIn("String", refs)  # java.lang builtin

    def test_robust_on_garbage_file(self):
        bogus = Path(self.tmp.name) / "Bogus.java"
        bogus.write_bytes(b"\x00\x01not java { ( unmatched")
        result = parse_java_source(bogus)
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
