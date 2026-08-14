import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ghost_scan import (
    AuthorityRule,
    ConfigError,
    PatternSpec,
    SuppressionRule,
    TruthRule,
    changed_only_paths,
    changed_since_paths,
    classify_authority,
    haunting_label,
    load_config,
    main,
    render_markdown,
    render_text,
    scan,
)


def truth(rule_id='db', patterns=None, severity=10):
    patterns = patterns or (PatternSpec('MongoDB'),)
    return TruthRule(rule_id, 'Database', 'PostgreSQL', tuple(patterns), severity)


class AuthorityTests(unittest.TestCase):
    def test_historical_wins_by_rule_order(self):
        rules = [
            AuthorityRule('archive/**', 'historical'),
            AuthorityRule('**/*.md', 'current'),
        ]
        self.assertEqual(classify_authority('archive/old.md', rules), 'historical')

    def test_default_authority_is_reference(self):
        self.assertEqual(classify_authority('notes.txt', []), 'reference')


class MatchingTests(unittest.TestCase):
    def test_substring_is_case_insensitive_and_backward_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('We still use mongodb here.\n', encoding='utf-8')
            result = scan(root, [], [truth()], context=0)
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(result.drift[0].matched.casefold(), 'mongodb')

    def test_phrase_does_not_match_inside_larger_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('XAPI v2Y is unrelated.\nAPI v2 is stale.\n', encoding='utf-8')
            t = TruthRule('api', 'API', 'v3', (PatternSpec('API v2', 'phrase'),), 7)
            result = scan(root, [], [t], context=0)
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(result.drift[0].line, 2)

    def test_regex_is_opt_in_and_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('Project   ROCKET is old.\n', encoding='utf-8')
            t = TruthRule('name', 'Name', 'Acme Relay', (PatternSpec(r'Project\s+Rocket', 'regex'),), 5)
            result = scan(root, [], [t], context=0)
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(result.drift[0].matched, 'Project   ROCKET')


class SuppressionTests(unittest.TestCase):
    def test_same_line_inline_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB <!-- drift-ignore: db -->\n', encoding='utf-8')
            result = scan(root, [], [truth()], context=0)
            self.assertEqual(len(result.drift), 0)
            self.assertEqual(len(result.suppressed), 1)
            self.assertEqual(result.suppressed[0].suppression_source, 'inline:same-line')

    def test_previous_line_inline_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('<!-- drift-ignore: db -->\nMongoDB is mentioned intentionally.\n', encoding='utf-8')
            result = scan(root, [], [truth()], context=0)
            self.assertEqual(len(result.suppressed), 1)
            self.assertEqual(result.suppressed[0].suppression_source, 'inline:previous-line')

    def test_inline_suppression_is_rule_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB API v2 <!-- drift-ignore: db -->\n', encoding='utf-8')
            api = TruthRule('api', 'API', 'v3', (PatternSpec('API v2'),), 7)
            result = scan(root, [], [truth(), api], context=0)
            self.assertEqual(len(result.suppressed), 1)
            self.assertEqual(result.suppressed[0].rule_id, 'db')
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(result.drift[0].rule_id, 'api')

    def test_config_suppression_records_reason_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'MIGRATION.md').write_text('MongoDB was the old database.\n', encoding='utf-8')
            suppressions = [SuppressionRule('MIGRATION.md', 'db', 'Intentional migration note')]
            result = scan(root, [], [truth()], suppressions, context=0)
            self.assertEqual(len(result.suppressed), 1)
            finding = result.suppressed[0]
            self.assertEqual(finding.suppression_reason, 'Intentional migration note')
            self.assertEqual(finding.suppression_source, 'config:MIGRATION.md')


class ContextAndReportingTests(unittest.TestCase):
    def test_context_defaults_to_one_line_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('before\nMongoDB\nafter\n', encoding='utf-8')
            result = scan(root, [], [truth()], context=1)
            finding = result.drift[0]
            self.assertEqual(finding.context_before, ((1, 'before'),))
            self.assertEqual(finding.context_after, ((3, 'after'),))

    def test_text_report_contains_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            result = scan(root, [AuthorityRule('README.md', 'current')], [truth()], context=0)
            rendered = render_text(result)
            self.assertIn('BY RULE', rendered)
            self.assertIn('BY AUTHORITY', rendered)
            self.assertIn('db', rendered)
            self.assertIn('current', rendered)

    def test_markdown_report_is_clean_and_contains_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            result = scan(root, [], [truth()], context=0)
            rendered = render_markdown(result)
            self.assertIn('# Repository Drift Report', rendered)
            self.assertIn('## Current drift', rendered)
            self.assertIn('`README.md:1`', rendered)

    def test_suppressed_hidden_unless_requested_in_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB <!-- drift-ignore: db -->\n', encoding='utf-8')
            result = scan(root, [], [truth()], context=0)
            self.assertNotIn('SUPPRESSED ECHO', render_text(result, show_suppressed=False))
            self.assertIn('SUPPRESSED ECHO', render_text(result, show_suppressed=True))


class ConfigValidationTests(unittest.TestCase):
    def write_config(self, root, data):
        path = Path(root) / 'truths.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_v01_string_patterns_still_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}]
            })
            _, truths, _ = load_config(path)
            self.assertEqual(truths[0].stale_patterns[0], PatternSpec('MongoDB', 'substring'))

    def test_duplicate_truth_ids_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [
                    {'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']},
                    {'id': 'db', 'canonical': 'SQLite', 'stale_patterns': ['MySQL']},
                ]
            })
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_empty_canonical_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [{'id': 'db', 'canonical': ' ', 'stale_patterns': ['MongoDB']}]
            })
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_unknown_match_mode_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': [
                    {'value': 'MongoDB', 'match': 'fuzzy'}
                ]}]
            })
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_malformed_regex_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': [
                    {'value': '[unterminated', 'match': 'regex'}
                ]}]
            })
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_config_suppression_requires_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}],
                'suppressions': [{'path': 'README.md', 'rule_id': 'db'}],
            })
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_config_suppression_must_reference_known_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}],
                'suppressions': [{'path': 'README.md', 'rule_id': 'api', 'reason': 'test'}],
            })
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_conflicting_duplicate_authority_patterns_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {
                'authority_rules': [
                    {'pattern': 'README.md', 'authority': 'current'},
                    {'pattern': 'README.md', 'authority': 'historical'},
                ],
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}],
            })
            with self.assertRaises(ConfigError):
                load_config(path)


class ScanBehaviorTests(unittest.TestCase):
    def test_current_drift_and_historical_echo_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'archive').mkdir()
            (root / 'README.md').write_text('We use MongoDB.\n', encoding='utf-8')
            (root / 'archive' / 'old.md').write_text('We used MongoDB.\n', encoding='utf-8')
            rules = [AuthorityRule('archive/**', 'historical'), AuthorityRule('README.md', 'current')]
            result = scan(root, rules, [truth()], context=0)
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(len(result.ghosts), 1)
            self.assertEqual(result.haunting_score, 10)

    def test_door_limits_scan_to_one_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            (root / 'NOTES.md').write_text('MongoDB\n', encoding='utf-8')
            result = scan(root, [], [truth()], door='README.md', context=0)
            self.assertEqual(result.file_count, 1)
            self.assertEqual(len(result.drift), 1)

    def test_included_paths_limits_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            (root / 'NOTES.md').write_text('MongoDB\n', encoding='utf-8')
            result = scan(root, [], [truth()], included_paths={'NOTES.md'}, context=0)
            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.drift[0].path, 'NOTES.md')


class GitTests(unittest.TestCase):
    def git(self, root, *args):
        subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True)

    def make_repo(self, tmp):
        root = Path(tmp)
        self.git(root, 'init', '-q')
        self.git(root, 'config', 'user.email', 'test@example.com')
        self.git(root, 'config', 'user.name', 'Test')
        (root / 'README.md').write_text('clean\n', encoding='utf-8')
        self.git(root, 'add', 'README.md')
        self.git(root, 'commit', '-q', '-m', 'initial')
        return root

    def test_changed_only_includes_modified_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            (root / 'README.md').write_text('changed\n', encoding='utf-8')
            (root / 'NEW.md').write_text('new\n', encoding='utf-8')
            paths = changed_only_paths(root)
            self.assertEqual(paths, {'README.md', 'NEW.md'})

    def test_changed_since_uses_ref_to_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp)
            base = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            (root / 'SECOND.md').write_text('second\n', encoding='utf-8')
            self.git(root, 'add', 'SECOND.md')
            self.git(root, 'commit', '-q', '-m', 'second')
            paths = changed_since_paths(root, base)
            self.assertEqual(paths, {'SECOND.md'})


class CliTests(unittest.TestCase):
    def test_exit_code_two_on_drift_and_zero_when_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            repo.mkdir()
            config = root / 'truths.json'
            config.write_text(json.dumps({
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}]
            }), encoding='utf-8')
            (repo / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(repo), '--config', str(config), '--context', '0']), 2)
            (repo / 'README.md').write_text('PostgreSQL\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(repo), '--config', str(config), '--context', '0']), 0)

    def test_output_file_is_written_only_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            repo.mkdir()
            config = root / 'truths.json'
            config.write_text(json.dumps({
                'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}]
            }), encoding='utf-8')
            (repo / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            output = root / 'report.md'
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([str(repo), '--config', str(config), '--report', 'markdown', '--output', str(output)])
            self.assertEqual(code, 2)
            self.assertTrue(output.exists())
            self.assertIn('# Repository Drift Report', output.read_text(encoding='utf-8'))


class ScoreTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(haunting_label(0), 'Quiet')
        self.assertEqual(haunting_label(30), 'Haunted')
        self.assertEqual(haunting_label(101), 'CALL THE ARCHITECT')


if __name__ == '__main__':
    unittest.main()
