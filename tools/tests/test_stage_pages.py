import importlib.util
import contextlib
import io
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('stage_pages', Path(__file__).parents[1] / 'stage-pages.py')
stage_pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_pages)
SHA = 'a' * 40


class StagePagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source'
        self.output = Path(self.temp.name) / 'site'
        self.source.mkdir()
        self.put('index.html', '<html><body>Dashboard</body></html>')
        self.put('reports/history/index.html', '<a href="2026-10-01-abc/linux/index.html">History</a>')
        self.put('reports/history/2026-10-01-abc/linux/index.html', 'historical HTML')
        self.put('reports/history/2026-10-01-abc/linux/huge.html', 'historical source')
        self.put('reports/history/2026-10-01-abc/linux/coverage-summary.json', '{"line_coverage":"50"}')
        self.put('reports/history/2026-01-01-abc/macos/coverage-summary.json', '{}')
        self.put('reports/slangc-coverage-trend.html', 'trend')
        self.put('reports/coverage-data.json', '[]')
        self.put('reports/latest/combined-summary.json', json.dumps({'platforms': {'windows': {'line_coverage': '50'}}}))
        self.put('reports/latest/coverage/stale.html', 'stale legacy report')
        for view in stage_pages.VIEWS:
            self.put(f'reports/latest/{view}/index.html', '<a href="file.html#L1">File</a>')
            self.put(f'reports/latest/{view}/file.html', '<pre id="L1">code</pre>')
            self.put(f'reports/latest/{view}/coverage.lcov', 'raw data')

    def put(self, relative, content):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_views_metadata_and_archive_routes_without_changing_source(self):
        before = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        stage_pages.stage(self.source, self.output, SHA)
        for view in stage_pages.VIEWS:
            self.assertEqual((self.output / f'reports/latest/{view}/file.html').read_text(), '<pre id="L1">code</pre>')
            self.assertFalse((self.output / f'reports/latest/{view}/coverage.lcov').exists())
        self.assertFalse((self.output / 'reports/latest/coverage').exists())
        self.assertIn('retained files', (self.output / 'reports/history/2026-01-01-abc/macos/index.html').read_text())
        historical = self.output / 'reports/history/2026-10-01-abc/linux'
        self.assertFalse((historical / 'huge.html').exists())
        self.assertIn(SHA, (historical / 'index.html').read_text())
        self.assertIn('50', (historical / 'coverage-summary.json').read_text())
        self.assertIn('new/full/index.html', (self.output / 'reports/latest/linux/index.html').read_text())
        self.assertIn('../new/slangc/index.html', (self.output / 'reports/latest/linux/slangc/index.html').read_text())
        after = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_warning_summary_and_publication_marker(self):
        summary = Path(self.temp.name) / "summary.md"
        output = io.StringIO()
        with patch.object(stage_pages, "WARN_CONTENT_BYTES", 1), \
                patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), \
                contextlib.redirect_stdout(output):
            stage_pages.stage(self.source, self.output, SHA)
        self.assertIn("::warning::Pages content", output.getvalue())
        self.assertIn("byte budget", summary.read_text())
        self.assertEqual(json.loads((self.output / "reports/publication.json").read_text()),
                         {"report_commit": SHA})

    def test_windows_is_optional_only_when_summary_has_no_result(self):
        self.put('reports/latest/combined-summary.json', '{"platforms":{"windows":{}}}')
        shutil.rmtree(self.source / 'reports/latest/windows')
        stage_pages.stage(self.source, self.output, SHA)
        self.assertIn('Windows coverage is unavailable',
                      (self.output / 'reports/latest/index.html').read_text())
        self.assertIn('No Windows result',
                      (self.output / 'reports/latest/windows/index.html').read_text())
        self.assertFalse((self.output / 'reports/latest/windows/new').exists())

    def test_missing_view_fails(self):
        (self.source / 'reports/latest/windows/new/full/index.html').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing current report'):
            stage_pages.stage(self.source, self.output, SHA)
        self.assertFalse(self.output.exists())

    def test_symlink_rejected(self):
        (self.source / 'reports/latest/linux/new/full/outside.html').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'Not a regular'):
            stage_pages.stage(self.source, self.output, SHA)

    def test_budget_fails(self):
        with self.assertRaisesRegex(ValueError, 'size budget exceeded'):
            stage_pages.stage(self.source, self.output, SHA, max_bytes=1)

    def test_source_and_existing_output_protected(self):
        for output in (self.source, self.source / 'site', self.source.parent):
            with self.assertRaisesRegex(ValueError, 'separate'):
                stage_pages.stage(self.source, output, SHA)
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            stage_pages.stage(self.source, self.output, SHA)

    def test_revision_must_be_pinned(self):
        with self.assertRaisesRegex(ValueError, 'full Git commit SHA'):
            stage_pages.stage(self.source, self.output, 'main')


if __name__ == '__main__':
    unittest.main()
