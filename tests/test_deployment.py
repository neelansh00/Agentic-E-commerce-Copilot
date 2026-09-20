"""Deployment asset loading must not overwrite local data or trust archive paths."""
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from app.deployment import REQUIRED, digest, install_bundle, ensure_assets


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'bundle.zip'

    def bundle(self, extra=None):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name in REQUIRED:
                archive.writestr(name, b'fixture')
            if extra is not None:
                archive.writestr(extra, b'bad')
        return digest(self.archive)

    def test_valid_install_and_cached_restart_do_not_download(self):
        checksum = self.bundle()
        install_bundle(self.archive, checksum, self.root)
        with patch.dict(os.environ, {'ASSET_BUNDLE_URL': 'https://example.org/assets.zip',
                                    'ASSET_BUNDLE_SHA256': checksum}), patch('app.deployment.urlopen') as get:
            ensure_assets(self.root)
            get.assert_not_called()

    def test_hash_failure_leaves_no_data(self):
        self.bundle()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            install_bundle(self.archive, '0' * 64, self.root)
        self.assertFalse((self.root / 'data').exists())

    def test_traversal_absolute_and_unexpected_paths(self):
        for name in ['../escape', '/escape', 'models/bge-small-en-v1.5/../../escape',
                     'processed\\escape', 'processed/C:escape', '.env']:
            checksum = self.bundle(name)
            with self.assertRaises(ValueError):
                install_bundle(self.archive, checksum, self.root)
            self.assertFalse((self.root / 'data').exists())

    def test_symlink_rejected(self):
        link = zipfile.ZipInfo('models/bge-small-en-v1.5/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        checksum = self.bundle(link)
        with self.assertRaises(ValueError):
            install_bundle(self.archive, checksum, self.root)

    def test_size_limit_and_missing_files(self):
        checksum = self.bundle()
        with patch('app.deployment.MAX_BYTES', 1), self.assertRaises(ValueError):
            install_bundle(self.archive, checksum, self.root)
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('processed/olist.sqlite', 'fixture')
        with self.assertRaises(ValueError):
            install_bundle(self.archive, digest(self.archive), self.root)

    def test_existing_local_data_preserved(self):
        checksum = self.bundle()
        (self.root / 'data').mkdir()
        sentinel = self.root / 'data/keep'
        sentinel.write_text('original')
        with self.assertRaises(ValueError):
            install_bundle(self.archive, checksum, self.root)
        self.assertEqual(sentinel.read_text(), 'original')

    def test_local_assets_need_no_network(self):
        for name in REQUIRED:
            path = self.root / 'data' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        with patch.dict(os.environ, {'ASSET_BUNDLE_URL': ''}), patch('app.deployment.urlopen') as get:
            ensure_assets(self.root)
            get.assert_not_called()

    def test_download_and_network_error_sanitization(self):
        checksum = self.bundle()
        class Response(io.BytesIO):
            def geturl(self):
                return 'https://example.org/assets.zip'
        env = {'ASSET_BUNDLE_URL': 'https://example.org/assets.zip?secret=value',
               'ASSET_BUNDLE_SHA256': checksum}
        with patch.dict(os.environ, env), patch('app.deployment.urlopen', side_effect=RuntimeError('secret=value')):
            with self.assertRaises(ValueError) as error:
                ensure_assets(self.root)
            self.assertNotIn('secret', str(error.exception))
        with patch.dict(os.environ, env), patch('app.deployment.urlopen', return_value=Response(self.archive.read_bytes())):
            ensure_assets(self.root)
        self.assertTrue((self.root / 'data/.bundle.sha256').exists())

    def test_http_and_missing_hash_rejected_before_download(self):
        for url, checksum in [('http://example.org/data', '0' * 64), ('https://example.org/data', '')]:
            with patch.dict(os.environ, {'ASSET_BUNDLE_URL': url, 'ASSET_BUNDLE_SHA256': checksum}), patch('app.deployment.urlopen') as get:
                with self.assertRaises(ValueError):
                    ensure_assets(self.root)
                get.assert_not_called()
