import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ci_compile import compile_budget

class SplitFinalArchiveBudgetTests(unittest.TestCase):
    def test_completion_job_reserves_delta_not_full_archive(self):
        # Completion captures an independent delta. Full archive work belongs
        # to a separate job, so 17 minutes restore still leaves compile time.
        self.assertEqual(compile_budget(17 * 60, False), 840)

    def test_normal_full_budget_unchanged(self):
        self.assertEqual(compile_budget(0, False), 1500)
        self.assertEqual(compile_budget(600, False), 1260)
        self.assertEqual(compile_budget(600, True), 960)

if __name__ == '__main__':
    unittest.main()
