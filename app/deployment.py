"""Install an owner-configured, checksummed runtime bundle; never accepts chat input."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import threading
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 800 * 1024 * 1024
LOCK = threading.Lock()
REQUIRED = {'processed/olist.sqlite', 'processed/knowledge_index/current.json',
            'models/bge-small-en-v1.5/manifest.json'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def allowed(name):
    path = PurePosixPath(name)
    return (not path.is_absolute() and '\\' not in name and ':' not in name
            and all(p not in ('', '.', '..') for p in name.split('/'))
            and (name == 'processed/olist.sqlite'
                 or (len(path.parts) == 3 and path.parts[:2] in
                     [('processed', 'knowledge_index'), ('models', 'bge-small-en-v1.5')])))


def install_bundle(archive, expected_hash, root=ROOT):
    """Validate before publishing a whole data directory. Never overwrite local data."""
    root = Path(root)
    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected_hash or ''):
        raise ValueError('Set ASSET_BUNDLE_SHA256 to the exported SHA-256.')
    if digest(archive) != expected_hash.lower():
        raise ValueError('Asset bundle checksum mismatch.')
    if (root / 'data').exists():
        raise ValueError('Existing data directory is preserved; use a fresh deployment for a new bundle.')
    with tempfile.TemporaryDirectory(prefix='bundle-', dir=root) as temporary:
        staged = Path(temporary) / 'data'
        staged.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            files = bundle.infolist()
            names = [f.filename for f in files]
            if (len(files) > 100 or len(set(names)) != len(names)
                    or not REQUIRED <= set(names)
                    or sum(f.file_size for f in files) > MAX_BYTES):
                raise ValueError('Incomplete, duplicate or oversized asset bundle.')
            for item in files:
                if not allowed(item.filename) or stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError('Invalid asset bundle path or link.')
            for item in files:
                target = staged / item.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
        (staged / '.bundle.sha256').write_text(expected_hash.lower(), encoding='ascii')
        staged.replace(root / 'data')


def ensure_assets(root=ROOT):
    """No network activity unless deployment owner explicitly configures a bundle URL."""
    root = Path(root)
    url = os.getenv('ASSET_BUNDLE_URL', '').strip()
    if not url:
        if not all((root / 'data' / name).is_file() for name in REQUIRED):
            raise ValueError('Prepare local data/model/index or configure ASSET_BUNDLE_URL and ASSET_BUNDLE_SHA256.')
        return
    expected = os.getenv('ASSET_BUNDLE_SHA256', '').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Set ASSET_BUNDLE_SHA256 to the exported SHA-256.')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('Asset bundle URL must be HTTPS without embedded credentials.')
    with LOCK:
        marker = root / 'data/.bundle.sha256'
        if marker.exists() and marker.read_text(encoding='ascii').strip() == expected:
            if all((root / 'data' / name).is_file() for name in REQUIRED):
                return
        if (root / 'data').exists():
            raise ValueError('Existing data is preserved; deploy to a fresh instance to change bundles.')
        try:
            with tempfile.TemporaryDirectory(prefix='download-', dir=root) as temporary:
                archive = Path(temporary) / 'assets.zip'
                with urlopen(url, timeout=60) as response, archive.open('wb') as output:
                    if urlparse(response.geturl()).scheme != 'https':
                        raise ValueError('HTTPS is required after redirects.')
                    count = 0
                    while chunk := response.read(1024 * 1024):
                        count += len(chunk)
                        if count > MAX_BYTES:
                            raise ValueError('Asset download exceeds size limit.')
                        output.write(chunk)
                install_bundle(archive, expected, root)
        except Exception:
            # Signed URLs may carry credentials: never expose an underlying network exception.
            raise ValueError('Asset setup failed. Check the owner-configured URL, SHA-256 and bundle contents.') from None
