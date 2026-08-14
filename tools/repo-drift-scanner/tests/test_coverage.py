import json
import tempfile
import unittest
from pathlib import Path

from drift_core import (
    AuthorityRule,
    PatternSpec,
    SuppressionRule,
    TruthRule,
    classify_authority,
    iter_text_files,
    scan,
)
from drift_coverage import analyze_coverage, decorate_report


def truth(pattern='MongoDB', canonical='PostgreSQL', rule_id='db'):
    return TruthRule(
        rule_id,
        'Declared current truth',
        canonical,
        (PatternSpec(pattern, 'substring'),),
        10,
    )


class FormatCoverageTests(unittest.TestCase):
    def test_rst_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.rst').write_text('MongoDB is current.\n', encoding='utf-8')
            result = scan(root, [AuthorityRule('README.rst', 'current')], [truth()], context=0)
            self.assertEqual(result.file_count, 1)
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(result.drift[0].path, 'README.rst')

    def test_extensionless_readme_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README').write_text('MongoDB\n', encoding='utf-8')
            result = scan(root, [AuthorityRule('README', 'current')], [truth()], context=0)
            self.assertEqual(result.file_count, 1)
            self.assertEqual(len(result.drift), 1)

    def test_extensionless_version_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'VERSION').write_text('1.0-old\n', encoding='utf-8')
            result = scan(
                root,
                [AuthorityRule('VERSION', 'current')],
                [truth('1.0-old', '2.0', 'version')],
                context=0,
            )
            self.assertEqual(len(result.drift), 1)

    def test_rst_history_filename_convention(self):
        self.assertEqual(classify_authority('MIGRATION_HISTORY.rst', []), 'historical')
        self.assertEqual(classify_authority('BUILD_LOG.rst', []), 'historical')
        self.assertEqual(classify_authority('DESIGN_ARCHIVE.rst', []), 'historical')

    def test_supported_file_listing_includes_rst_and_extensionless(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('README.rst', 'VERSION', 'README', 'notes.md'):
                (root / name).write_text('x', encoding='utf-8')
            names = {p.name for p in iter_text_files(root)}
            self.assertEqual(names, {'README.rst', 'VERSION', 'README', 'notes.md'})


class CoverageAccountingTests(unittest.TestCase):
    def test_high_value_ignored_adoc_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.adoc').write_text('important', encoding='utf-8')
            (root / 'notes.md').write_text('supported', encoding='utf-8')
            cov = analyze_coverage(root)
            self.assertEqual(cov.discovered_count, 2)
            self.assertEqual(cov.scanned_count, 1)
            self.assertEqual(cov.ignored_count, 1)
            self.assertEqual(cov.high_value_ignored, ('README.adoc',))
            self.assertEqual(dict(cov.ignored_by_type), {'.adoc': 1})

    def test_binary_readme_image_is_not_a_high_value_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.png').write_bytes(b'\x89PNG\r\n')
            cov = analyze_coverage(root)
            self.assertEqual(cov.discovered_count, 0)
            self.assertEqual(cov.high_value_ignored, ())

    def test_ordinary_ignored_source_is_counted_but_not_high_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'main.rs').write_text('fn main() {}', encoding='utf-8')
            cov = analyze_coverage(root)
            self.assertEqual(cov.discovered_count, 1)
            self.assertEqual(cov.scanned_count, 0)
            self.assertEqual(cov.ignored_count, 1)
            self.assertEqual(dict(cov.ignored_by_type), {'.rs': 1})
            self.assertEqual(cov.high_value_ignored, ())

    def test_coverage_respects_included_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.adoc').write_text('ignored', encoding='utf-8')
            (root / 'README.rst').write_text('scanned', encoding='utf-8')
            cov = analyze_coverage(root, included_paths={'README.rst'})
            self.assertEqual(cov.scope, 'filtered')
            self.assertEqual(cov.discovered_count, 1)
            self.assertEqual(cov.scanned_count, 1)
            self.assertEqual(cov.high_value_ignored, ())

    def test_coverage_respects_door(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.adoc').write_text('ignored', encoding='utf-8')
            (root / 'README.rst').write_text('scanned', encoding='utf-8')
            cov = analyze_coverage(root, door='README.adoc')
            self.assertEqual(cov.scope, 'door')
            self.assertEqual(cov.discovered_count, 1)
            self.assertEqual(cov.scanned_count, 0)
            self.assertEqual(cov.high_value_ignored, ('README.adoc',))

    def test_json_decoration_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.adoc').write_text('ignored', encoding='utf-8')
            cov = analyze_coverage(root)
            payload = json.loads(decorate_report('{"ok": true}\n', 'json', cov))
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['coverage']['files_ignored'], 1)
            self.assertEqual(payload['coverage']['high_value_ignored'], ['README.adoc'])

    def test_markdown_decoration_contains_coverage_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.rst').write_text('ok', encoding='utf-8')
            decorated = decorate_report('# Report\n', 'markdown', analyze_coverage(root))
            self.assertIn('## Coverage', decorated)
            self.assertIn('**Files scanned:** 1', decorated)

    def test_text_decoration_contains_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.rst').write_text('ok', encoding='utf-8')
            decorated = decorate_report('report\n', 'text', analyze_coverage(root))
            self.assertIn('FILES DISCOVERED      1', decorated)
            self.assertIn('FILES SCANNED         1', decorated)


class ExternalRegressionTests(unittest.TestCase):
    def test_faker_style_rst_drift_is_now_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.rst').write_text(
                'Starting from version 5.0.0, Faker only supports Python 3.8 and above.\n',
                encoding='utf-8',
            )
            rule = TruthRule(
                'python-support',
                'Current Python support floor',
                'Python >= 3.10',
                (PatternSpec('only supports Python 3.8 and above', 'phrase'),),
                10,
                'setup.py',
                None,
                'setup.py declares python_requires=">=3.10"',
            )
            result = scan(
                root,
                [AuthorityRule('README.rst', 'current')],
                [rule],
                context=0,
            )
            self.assertEqual(len(result.drift), 1)
            self.assertEqual(result.drift[0].canonical_source, 'setup.py')

    def test_v02_demo_behavior_remains_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'archive').mkdir()
            (root / 'README.md').write_text(
                '# Acme Relay\n\nThe application uses MongoDB for persistent data.\nClients should call API v2.\n',
                encoding='utf-8',
            )
            (root / 'MIGRATION.md').write_text(
                '# Migration\n\nMongoDB was the previous primary database.\n', encoding='utf-8'
            )
            (root / 'NOTES.md').write_text(
                '<!-- drift-ignore: project-name -->\nThe old Project Rocket name is intentional.\n',
                encoding='utf-8',
            )
            (root / 'archive' / '2025-plan.md').write_text(
                'At the time, the prototype used MongoDB and the working name was Project Rocket.\n',
                encoding='utf-8',
            )
            db = TruthRule('database', 'Database', 'PostgreSQL', (PatternSpec('MongoDB'),), 10)
            api = TruthRule('api-version', 'API', 'v3', (PatternSpec('API v2', 'phrase'),), 7)
            name = TruthRule(
                'project-name', 'Name', 'Acme Relay',
                (PatternSpec(r'Project\s+Rocket', 'regex'),), 5
            )
            result = scan(
                root,
                [AuthorityRule('archive/**', 'historical'), AuthorityRule('README.md', 'current')],
                [db, api, name],
                [SuppressionRule('MIGRATION.md', 'database', 'intentional migration note')],
                context=0,
            )
            self.assertEqual(len(result.drift), 2)
            self.assertEqual(len(result.ghosts), 2)
            self.assertEqual(len(result.suppressed), 2)
            self.assertEqual(result.haunting_score, 17)


if __name__ == '__main__':
    unittest.main()
