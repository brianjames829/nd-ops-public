from pathlib import Path
import tempfile
import unittest

from ghost_scan import AuthorityRule, TruthRule, classify_authority, haunting_label, scan


class AuthorityTests(unittest.TestCase):
    def test_historical_wins(self):
        rules = [
            AuthorityRule('archive/**', 'historical'),
            AuthorityRule('**/*.md', 'current'),
        ]
        self.assertEqual(classify_authority('archive/old.md', rules), 'historical')


class ScanTests(unittest.TestCase):
    def test_current_drift_and_historical_echo_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'archive').mkdir()
            (root / 'README.md').write_text('We use MongoDB.\n', encoding='utf-8')
            (root / 'archive' / 'old.md').write_text('We used MongoDB.\n', encoding='utf-8')

            authority_rules = [
                AuthorityRule('archive/**', 'historical'),
                AuthorityRule('README.md', 'current'),
            ]
            truths = [TruthRule('db', 'Database', 'PostgreSQL', ('MongoDB',), 10)]
            findings, count = scan(root, authority_rules, truths)

            self.assertEqual(count, 2)
            self.assertEqual(sum(f.kind == 'current_drift' for f in findings), 1)
            self.assertEqual(sum(f.kind == 'harmless_ghost' for f in findings), 1)
            self.assertEqual(sum(f.score for f in findings), 10)

    def test_door_limits_scan_to_one_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            (root / 'NOTES.md').write_text('MongoDB\n', encoding='utf-8')
            rules = [AuthorityRule('README.md', 'current')]
            truths = [TruthRule('db', 'Database', 'PostgreSQL', ('MongoDB',), 10)]
            findings, count = scan(root, rules, truths, door='README.md')
            self.assertEqual(count, 1)
            self.assertEqual(len(findings), 1)


class ScoreTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(haunting_label(0), 'Quiet')
        self.assertEqual(haunting_label(30), 'Haunted')
        self.assertEqual(haunting_label(101), 'CALL THE ARCHITECT')


if __name__ == '__main__':
    unittest.main()
