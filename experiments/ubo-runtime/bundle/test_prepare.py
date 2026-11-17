import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prepare', HERE / 'prepare.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PrepareTest(unittest.TestCase):
    def test_complete_reproducible_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a.zip', Path(d)/'b.zip'
            first = module.prepare(HERE/'.cache'/'uBlock0_1.76.4.chromium.zip', a)
            module.prepare(HERE/'.cache'/'uBlock0_1.76.4.chromium.zip', b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(first['file_count'], 668)
            self.assertFalse(first['runtime_enabled'])
            self.assertEqual(first['bundle_sha256'], '580afa3547a46422b3752759b5a90018ba7bfa4320770ea863950c78b29932d5')
            with zipfile.ZipFile(a) as z:
                self.assertEqual(json.loads(z.read('manifest.json'))['version'], '1.76.4')
                self.assertIn(b'GNU GENERAL PUBLIC LICENSE', z.read('LICENSE.txt'))

    def test_tampered_archive_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d)/'bad.zip', Path(d)/'output.zip'
            source.write_bytes((HERE/'.cache'/'uBlock0_1.76.4.chromium.zip').read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                module.prepare(source, output, cache_dir=HERE/'.cache')
            self.assertFalse(output.exists())

    def test_wrong_inventory_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            lock = json.loads((HERE/'lock.json').read_text())
            del lock['files']['js/start.js']
            p = Path(d)/'lock.json'; p.write_text(json.dumps(lock))
            output = Path(d)/'output.zip'
            with self.assertRaisesRegex(ValueError, 'inventory mismatch'):
                module.prepare(HERE/'.cache'/'uBlock0_1.76.4.chromium.zip', output, p)
            self.assertFalse(output.exists())

    def test_existing_output_not_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'output.zip'; p.write_bytes(b'keep')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                module.prepare(HERE/'.cache'/'uBlock0_1.76.4.chromium.zip', p)
            self.assertEqual(p.read_bytes(), b'keep')

    def test_fetch_uses_only_exact_locked_urls_and_reuses_valid_cache(self):
        lock = json.loads((HERE/'lock.json').read_text())
        def download(args, **kwargs):
            self.assertEqual(kwargs['timeout'], 65)
            self.assertIn('--max-filesize', args)
            url = args[-1]
            filename = module.ARCHIVE if url == lock['archive_url'] else module.SOURCE
            self.assertIn(url, [lock['archive_url'], lock['source_url']])
            Path(args[args.index('--output') + 1]).write_bytes((HERE/'.cache'/filename).read_bytes())
        with tempfile.TemporaryDirectory() as d, patch.object(module.subprocess, 'run', side_effect=download) as fetch:
            module.materialize(d)
            module.materialize(d)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(len(list(Path(d).iterdir())), 2)

    def test_failed_fetch_leaves_no_partial_archive(self):
        def download(args, **kwargs):
            Path(args[args.index('--output') + 1]).write_bytes(b'bad')
        with tempfile.TemporaryDirectory() as d, patch.object(module.subprocess, 'run', side_effect=download):
            with self.assertRaisesRegex(ValueError, 'download digest mismatch'):
                module.materialize(d)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_corresponding_source_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            details = Path(d)/'details'; details.write_text('Pinned preparation only; no runtime changes.')
            target = Path(d)/'artifacts'
            module.export_corresponding_source(HERE/'.cache', target, details)
            self.assertEqual((target/module.SOURCE).read_bytes(), (HERE/'.cache'/module.SOURCE).read_bytes())
            self.assertEqual((target/'sandium-integration-details.txt').read_text(), details.read_text())
            self.assertTrue((target/'LICENSE.txt').is_file())

if __name__ == '__main__': unittest.main()
