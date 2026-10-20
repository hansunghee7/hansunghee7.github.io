"""check_saegim_names.py 시험: 세기와 비교 규칙."""
import unittest

import check_saegim_names as m


class CountTest(unittest.TestCase):
    def test_counts_both_spellings_case_insensitive(self):
        self.assertEqual(m.count_text("Saegim 새김 SAEGIM_TOKEN carvit"), 3)

    def test_zero_when_clean(self):
        self.assertEqual(m.count_text("carvit only"), 0)


class CompareTest(unittest.TestCase):
    def test_new_file_is_worse(self):
        worse, better = m.compare({"a.py": 2}, {})
        self.assertEqual(worse, {"a.py": (0, 2)})
        self.assertEqual(better, {})

    def test_increase_is_worse(self):
        worse, _ = m.compare({"a.py": 3}, {"a.py": 2})
        self.assertEqual(worse, {"a.py": (2, 3)})

    def test_decrease_is_better_and_passes(self):
        worse, better = m.compare({"a.py": 1}, {"a.py": 2, "b.py": 4})
        self.assertEqual(worse, {})
        self.assertEqual(better, {"a.py": (2, 1), "b.py": (4, 0)})

    def test_same_is_clean(self):
        worse, better = m.compare({"a.py": 2}, {"a.py": 2})
        self.assertEqual((worse, better), ({}, {}))


if __name__ == "__main__":
    unittest.main()
