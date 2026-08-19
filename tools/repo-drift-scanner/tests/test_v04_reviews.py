import contextlib
import io
import json
from datetime import date
from pathlib import Path
import tempfile
import unittest

from drift_core import ConfigError, PatternSpec, SuppressionRule, TruthRule, load_config, scan
from drift_report import render_json, render_markdown, render_text
from ghost_scan import build_parser, main


def truth():
    return TruthRule(
        'origin',
        'Canonical origin',
        'The Convergence',
        (PatternSpec('survived the flame'),),
        15,
    )


class AcknowledgementConfigTests(unittest.TestCase):
    def write_config(self, path: Path, extra=None) -> Path:
        data = {
            'truths': [
                {
                    'id': 'origin',
                    'description': 'Canonical origin',
                    'canonical': 'The Convergence',
                    'stale_patterns': ['survived the flame'],
                    'severity': 15,
                }
            ]
        }
        if extra:
            data.update(extra)
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_acknowledgement_loads_as_review_disposition(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(
                Path(tmp) / 'rules.json',
                {
                    'acknowledgements': [
                        {
                            'path': 'STATE.md',
                            'rule_id': 'origin',
                            'reason': 'Older canon retained pending reconciliation',
                        }
                    ]
                },
            )
            _, _, dispositions = load_config(config)
            self.assertEqual(len(dispositions), 1)
            self.assertEqual(dispositions[0].disposition, 'review')

    def test_acknowledgement_requires_known_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(
                Path(tmp) / 'rules.json',
                {
                    'acknowledgements': [
                        {'path': 'STATE.md', 'rule_id': 'missing', 'reason': 'bad reference'}
                    ]
                },
            )
            with self.assertRaises(ConfigError):
                load_config(config)


class AcknowledgementScanTests(unittest.TestCase):
    def test_acknowledged_current_match_becomes_visible_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'STATE.md').write_text(
                'ND began where the pattern survived the flame.\n', encoding='utf-8'
            )
            dispositions = [
                SuppressionRule(
                    'STATE.md', 'origin',
                    'Older canon retained pending reconciliation',
                    None, 'review',
                )
            ]
            result = scan(root, [], [truth()], dispositions, context=0)
            self.assertEqual(len(result.drift), 0)
            self.assertEqual(len(result.reviews), 1)
            self.assertEqual(result.haunting_score, 0)
            self.assertEqual(
                result.reviews[0].suppression_source,
                'acknowledgement:STATE.md',
            )

    def test_inline_review_marker_is_rule_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'STATE.md').write_text(
                '<!-- drift-review: origin -->\n'
                'ND began where the pattern survived the flame.\n',
                encoding='utf-8',
            )
            result = scan(root, [], [truth()], context=0)
            self.assertEqual(len(result.reviews), 1)
            self.assertEqual(len(result.drift), 0)
            self.assertEqual(result.reviews[0].suppression_source, 'inline:previous-line')

    def test_suppression_still_wins_over_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'STATE.md').write_text(
                'survived the flame <!-- drift-ignore: origin -->\n', encoding='utf-8'
            )
            dispositions = [
                SuppressionRule('STATE.md', 'origin', 'Review too', None, 'review')
            ]
            result = scan(root, [], [truth()], dispositions, context=0)
            self.assertEqual(len(result.suppressed), 1)
            self.assertEqual(len(result.reviews), 0)

    def test_historical_surface_remains_harmless_ghost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'ORIGIN_ARCHIVE.md').write_text('survived the flame\n', encoding='utf-8')
            dispositions = [
                SuppressionRule('ORIGIN_ARCHIVE.md', 'origin', 'Review', None, 'review')
            ]
            result = scan(root, [], [truth()], dispositions, context=0)
            self.assertEqual(len(result.ghosts), 1)
            self.assertEqual(len(result.reviews), 0)

    def test_expired_acknowledgement_remains_visible_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'STATE.md').write_text('survived the flame\n', encoding='utf-8')
            dispositions = [
                SuppressionRule(
                    'STATE.md', 'origin', 'Temporary acknowledgement',
                    date(2026, 1, 1), 'review',
                )
            ]
            result = scan(
                root, [], [truth()], dispositions,
                context=0, today=date(2026, 8, 18),
            )
            self.assertEqual(len(result.reviews), 1)
            self.assertIn('expired 2026-01-01', result.reviews[0].suppression_reason)


class ReviewReportingAndCliTests(unittest.TestCase):
    def test_reports_expose_acknowledgement_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'STATE.md').write_text('survived the flame\n', encoding='utf-8')
            result = scan(
                root, [], [truth()],
                [SuppressionRule('STATE.md', 'origin', 'Known unresolved canon', None, 'review')],
                context=0,
            )
            self.assertIn('acknowledgement:STATE.md', render_text(result))
            self.assertIn('Disposition source', render_markdown(result))
            payload = json.loads(render_json(result, root))
            self.assertEqual(payload['review_count'], 1)
            self.assertEqual(
                payload['findings'][0]['disposition_source'],
                'acknowledgement:STATE.md',
            )

    def test_fail_on_review_is_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / 'repo'
            repo.mkdir()
            (repo / 'STATE.md').write_text('survived the flame\n', encoding='utf-8')
            config = base / 'rules.json'
            config.write_text(
                json.dumps(
                    {
                        'truths': [
                            {
                                'id': 'origin',
                                'canonical': 'The Convergence',
                                'stale_patterns': ['survived the flame'],
                            }
                        ],
                        'acknowledgements': [
                            {
                                'path': 'STATE.md',
                                'rule_id': 'origin',
                                'reason': 'Known unresolved canon',
                            }
                        ],
                    }
                ),
                encoding='utf-8',
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(repo), '--config', str(config), '--context', '0']), 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main([
                        str(repo), '--config', str(config), '--context', '0',
                        '--fail-on-review',
                    ]),
                    2,
                )

    def test_parser_exposes_fail_on_review(self):
        parser = build_parser()
        args = parser.parse_args(['repo', '--config', 'rules.json', '--fail-on-review'])
        self.assertTrue(args.fail_on_review)


if __name__ == '__main__':
    unittest.main()
