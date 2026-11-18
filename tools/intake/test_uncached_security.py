import unittest
from uncached_security import disposition


class ReviewDispositionTests(unittest.TestCase):
    def test_incomplete_pass_is_downgraded_and_missing_verdict_is_rejected(self):
        files={'a.py':'','b.py':'','c.py':''}
        report='### Verdict: PASS\nFiles reviewed: 3\na.py:1 b.py:2 c.py:3'
        self.assertEqual(disposition(report,files),'pass')
        self.assertEqual(disposition(report.replace('Files reviewed: 3','Files reviewed: 2'),files),'needs_review')
        self.assertEqual(disposition('### Verdict: FAIL',files),'fail')
        with self.assertRaises(ValueError):disposition('No verdict',files)


if __name__ == '__main__':
    unittest.main()
