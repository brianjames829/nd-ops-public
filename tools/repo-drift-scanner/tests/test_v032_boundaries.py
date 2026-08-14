import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from drift_core import AuthorityRule, PatternSpec, TruthRule, iter_text_files, load_exclude_paths, scan
from drift_coverage import analyze_coverage
from drift_scope import build_boundary
from ghost_scan import main


def config(path: Path, data):
    path.write_text(json.dumps(data), encoding='utf-8')


class V032BoundaryTests(unittest.TestCase):
    def test_active_config_inside_root_does_not_self_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            config(cfg, {'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}]})
            (root / 'README.md').write_text('PostgreSQL is current.\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = main([str(root), '--config', str(cfg), '--context', '0'])
            self.assertEqual(code, 0)
            self.assertIn('FILES EXCLUDED        1', out.getvalue())
            self.assertIn('auto:config', out.getvalue())

    def test_active_output_inside_root_does_not_poison_next_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            outp = root / 'drift-report.json'
            config(cfg, {'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}]})
            (root / 'README.md').write_text('MongoDB is current.\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), '--config', str(cfg), '--report', 'json', '--output', str(outp)]), 2)
            (root / 'README.md').write_text('PostgreSQL is current.\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), '--config', str(cfg), '--report', 'json', '--output', str(outp)]), 0)
            payload = json.loads(outp.read_text(encoding='utf-8'))
            self.assertEqual(payload['current_drift_count'], 0)
            self.assertGreaterEqual(payload['coverage']['files_excluded'], 2)

    def test_configured_exclude_paths_remove_test_fixture_from_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tests/fixtures').mkdir(parents=True)
            cfg = root / 'rules.json'
            config(cfg, {
                'exclude_paths': ['tests/fixtures/**'],
                'truths': [{'id': 'tesser', 'canonical': 'private', 'stale_patterns': ['public Tesser SaaS']}],
            })
            (root / 'tests/fixtures/case.py').write_text("x='public Tesser SaaS'\n", encoding='utf-8')
            (root / 'README.md').write_text('Tesser is private.\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = main([str(root), '--config', str(cfg)])
            self.assertEqual(code, 0)
            self.assertIn('tests/fixtures/**', out.getvalue())

    def test_cli_exclude_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            config(cfg, {'truths': [{'id': 'db', 'canonical': 'PostgreSQL', 'stale_patterns': ['MongoDB']}]})
            (root / 'fixture.md').write_text('MongoDB\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([str(root), '--config', str(cfg), '--exclude', 'fixture.md'])
            self.assertEqual(code, 0)

    def test_excluded_explicit_contract_target_is_config_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            config(cfg, {
                'exclude_paths': ['generated/**'],
                'contracts': [{'id': 'state', 'type': 'current_surface', 'path': 'generated/CURRENT_STATE.md'}],
            })
            (root / 'generated').mkdir()
            (root / 'generated/CURRENT_STATE.md').write_text('x\n', encoding='utf-8')
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main([str(root), '--config', str(cfg)])
            self.assertEqual(code, 3)
            self.assertIn('targets excluded path', err.getvalue())

    def test_markdown_extension_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.markdown').write_text('MongoDB\n', encoding='utf-8')
            truth = TruthRule('db', 'Database', 'PostgreSQL', (PatternSpec('MongoDB'),), 10)
            result = scan(root, [AuthorityRule('README.markdown', 'current')], [truth], context=0)
            self.assertEqual(len(result.drift), 1)

    def test_go_mod_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'go.mod').write_text('go 1.17\n', encoding='utf-8')
            truth = TruthRule('go', 'Go floor', 'go 1.22', (PatternSpec('go 1.17', 'phrase'),), 10)
            result = scan(root, [AuthorityRule('go.mod', 'current')], [truth], context=0)
            self.assertEqual(len(result.drift), 1)
            self.assertIn('go.mod', {p.name for p in iter_text_files(root)})

    def test_coverage_distinguishes_excluded_from_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            config(cfg, {
                'exclude_paths': ['tests/**'],
                'truths': [{'id': 'x', 'canonical': 'new', 'stale_patterns': ['old']}],
            })
            (root / 'tests').mkdir()
            (root / 'tests/case.md').write_text('old\n', encoding='utf-8')
            (root / 'README.adoc').write_text('text\n', encoding='utf-8')
            boundary = build_boundary(root, config_path=cfg, configured_patterns=load_exclude_paths(cfg))
            cov = analyze_coverage(root, boundary=boundary)
            self.assertEqual(cov.excluded_count, 2)
            self.assertEqual(cov.ignored_count, 1)
            self.assertEqual(cov.high_value_ignored, ('README.adoc',))

    def test_json_report_shows_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            config(cfg, {'truths': [{'id': 'x', 'canonical': 'new', 'stale_patterns': ['old']}]})
            (root / 'README.md').write_text('new\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main([str(root), '--config', str(cfg), '--report', 'json']), 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload['coverage']['files_excluded'], 1)
            self.assertEqual(payload['coverage']['excluded_by_rule'][0]['source'], 'auto:config')

    def test_no_contracts_still_honors_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'rules.json'
            config(cfg, {
                'exclude_paths': ['fixture.md'],
                'contracts': [{'id': 'a', 'type': 'authority', 'paths': ['README.md'], 'must_be': 'current'}],
            })
            (root / 'fixture.md').write_text('whatever\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), '--config', str(cfg), '--no-contracts']), 0)

    def test_version(self):
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main(['--version'])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn('0.3.2', out.getvalue())


if __name__ == '__main__':
    unittest.main()
