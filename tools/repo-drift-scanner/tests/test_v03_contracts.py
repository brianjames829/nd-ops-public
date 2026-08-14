import contextlib
import io
import json
from datetime import date
from pathlib import Path
import subprocess
import tempfile
import unittest

from drift_contracts import evaluate_contracts, load_contracts
from drift_core import AuthorityRule, PatternSpec, SuppressionRule, TruthRule, classify_authority, load_config, scan
from drift_report import render_json, render_markdown, render_text
from ghost_scan import main


def write_json(path, data):
    path.write_text(json.dumps(data), encoding='utf-8')


def evaluate(root, contracts, authorities=None, baseline=None):
    config = Path(root) / 'contracts.json'
    write_json(config, {'contracts': contracts})
    return evaluate_contracts(Path(root), authorities or [], load_contracts(config), baseline=baseline)


class AuthorityConventionTests(unittest.TestCase):
    def test_history_directory_is_historical(self):
        self.assertEqual(classify_authority('history/old.md', []), 'historical')

    def test_log_archive_and_history_suffixes_are_historical(self):
        self.assertEqual(classify_authority('WEBSITE_UPDATE_LOG.md', []), 'historical')
        self.assertEqual(classify_authority('ORIGIN_ARCHIVE.md', []), 'historical')
        self.assertEqual(classify_authority('PRICING_HISTORY.md', []), 'historical')

    def test_explicit_rule_overrides_convention(self):
        rules = [AuthorityRule('LIVE_LOG.md', 'current')]
        self.assertEqual(classify_authority('LIVE_LOG.md', rules), 'current')


class SuppressionExpiryTests(unittest.TestCase):
    def test_expired_suppression_becomes_nonblocking_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('MongoDB\n', encoding='utf-8')
            truth = TruthRule('db', 'Database', 'PostgreSQL', (PatternSpec('MongoDB'),), 10)
            suppressions = [SuppressionRule('README.md', 'db', 'temporary migration note', date(2026, 8, 13))]
            result = scan(root, [], [truth], suppressions, context=0, today=date(2026, 8, 14))
            self.assertEqual(len(result.drift), 0)
            self.assertEqual(len(result.reviews), 1)


class ContractValidationTests(unittest.TestCase):
    def test_authority_contract_detects_wrong_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'README.md').write_text('current\n', encoding='utf-8')
            result = evaluate(tmp, [{
                'id': 'current-readme', 'type': 'authority',
                'paths': ['README.md'], 'must_be': 'current'
            }])
            self.assertEqual(len(result.violations), 1)

    def test_structured_assertion_reads_json_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_json(Path(tmp) / 'state.json', {'tesser': {'public_product': True}})
            result = evaluate(tmp, [{
                'id': 'private-boundary', 'type': 'structured_assertion',
                'path': 'state.json', 'pointer': '/tesser/public_product',
                'op': 'equals', 'value': False
            }])
            self.assertEqual(len(result.violations), 1)

    def test_lifecycle_contract_catches_superseded_active_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'opportunities.jsonl').write_text(
                json.dumps({'id': 'old', 'status': 'active', 'superseded_by': 'new'}) + '\n',
                encoding='utf-8',
            )
            result = evaluate(tmp, [{
                'id': 'no-zombies', 'type': 'lifecycle', 'path': 'opportunities.jsonl',
                'invariants': [{
                    'when': {'field': 'superseded_by', 'op': 'exists', 'value': True},
                    'require': {'field': 'status', 'op': 'not_in', 'value': ['active', 'pending', 'open']},
                    'message': 'superseded record still has live status'
                }]
            }])
            self.assertEqual(len(result.violations), 1)

    def test_current_surface_supports_hard_and_review_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'CURRENT_STATE.md').write_text(
                'Tesser is private.\n## 2026-05-25 — Current Roadmap\n', encoding='utf-8'
            )
            result = evaluate(tmp, [{
                'id': 'current-state', 'type': 'current_surface', 'path': 'CURRENT_STATE.md',
                'must_be_authority': 'current',
                'required_patterns': ['Tesser is private'],
                'forbidden_patterns': ['public Tesser SaaS'],
                'review_patterns': [{'value': '^## 2026-05', 'match': 'regex'}]
            }], authorities=[AuthorityRule('CURRENT_STATE.md', 'current')])
            self.assertEqual(len(result.violations), 0)
            self.assertEqual(len(result.reviews), 1)

    def test_output_ownership_catches_wrong_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'scripts' / 'handoff.py').write_text("Path('briefs/latest_handoff.md')\n", encoding='utf-8')
            (root / 'scripts' / 'weekly.py').write_text("Path('briefs/latest_handoff.md')\n", encoding='utf-8')
            result = evaluate(tmp, [{
                'id': 'handoff-owner', 'type': 'output_ownership',
                'output': 'briefs/latest_handoff.md',
                'inspect': ['scripts/*.py'], 'owners': ['scripts/handoff.py']
            }])
            self.assertEqual(len(result.violations), 1)
            self.assertEqual(result.violations[0].path, 'scripts/weekly.py')

    def _git(self, root, *args):
        subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True)

    def _repo(self, tmp):
        root = Path(tmp)
        self._git(root, 'init', '-q')
        self._git(root, 'config', 'user.email', 'test@example.com')
        self._git(root, 'config', 'user.name', 'Test')
        (root / 'CHANGELOG.md').write_text('old history\n', encoding='utf-8')
        self._git(root, 'add', 'CHANGELOG.md')
        self._git(root, 'commit', '-q', '-m', 'baseline')
        return root

    def test_append_only_allows_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            (root / 'CHANGELOG.md').write_text('old history\nnew entry\n', encoding='utf-8')
            result = evaluate(tmp, [{
                'id': 'history-integrity', 'type': 'append_only', 'path': 'CHANGELOG.md'
            }], baseline='HEAD')
            self.assertEqual(len(result.findings), 0)

    def test_append_only_rejects_historical_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            (root / 'CHANGELOG.md').write_text('rewritten history\nnew entry\n', encoding='utf-8')
            result = evaluate(tmp, [{
                'id': 'history-integrity', 'type': 'append_only', 'path': 'CHANGELOG.md'
            }], baseline='HEAD')
            self.assertEqual(len(result.violations), 1)

    def test_append_only_without_baseline_is_review_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'CHANGELOG.md').write_text('history\n', encoding='utf-8')
            result = evaluate(tmp, [{
                'id': 'history-integrity', 'type': 'append_only', 'path': 'CHANGELOG.md'
            }])
            self.assertEqual(len(result.violations), 0)
            self.assertEqual(len(result.reviews), 1)


class ReportAndCliTests(unittest.TestCase):
    def test_reports_include_contract_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('clean\n', encoding='utf-8')
            config = root / 'config.json'
            write_json(config, {'contracts': [{
                'id': 'current-readme', 'type': 'authority',
                'paths': ['README.md'], 'must_be': 'current'
            }]})
            authorities, truths, suppressions = load_config(config)
            scan_result = scan(root, authorities, truths, suppressions)
            contract_result = evaluate_contracts(root, authorities, load_contracts(config))
            self.assertIn('CONTRACT VIOLATIONS  1', render_text(scan_result, contract_result=contract_result))
            self.assertIn('## Contract violations', render_markdown(scan_result, contract_result=contract_result))
            payload = json.loads(render_json(scan_result, root, contract_result=contract_result))
            self.assertEqual(payload['contract_violation_count'], 1)

    def test_cli_exit_two_on_contract_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('clean\n', encoding='utf-8')
            config = root / 'config.json'
            write_json(config, {'contracts': [{
                'id': 'current-readme', 'type': 'authority',
                'paths': ['README.md'], 'must_be': 'current'
            }]})
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), '--config', str(config)]), 2)

    def test_review_signal_does_not_fail_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'CURRENT_STATE.md').write_text('old section\n', encoding='utf-8')
            config = root / 'config.json'
            write_json(config, {'contracts': [{
                'id': 'review-old-section', 'type': 'current_surface',
                'path': 'CURRENT_STATE.md', 'review_patterns': ['old section']
            }]})
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), '--config', str(config)]), 0)

    def test_no_contracts_flag_preserves_text_only_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('clean\n', encoding='utf-8')
            config = root / 'config.json'
            write_json(config, {'contracts': [{
                'id': 'current-readme', 'type': 'authority',
                'paths': ['README.md'], 'must_be': 'current'
            }]})
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), '--config', str(config), '--no-contracts']), 0)


if __name__ == '__main__':
    unittest.main()
