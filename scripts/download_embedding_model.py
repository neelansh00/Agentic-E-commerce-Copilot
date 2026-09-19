"""One-time public embedding-weight download; no inference/API credentials needed."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'data/models/bge-small-en-v1.5'


def main():
    os.environ.setdefault('HF_HOME', str(ROOT / 'data/models/huggingface'))
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    from huggingface_hub import snapshot_download
    revision = '52398278842ec682c6f32300af41344b1c0b0bb2'
    repository = 'Qdrant/bge-small-en-v1.5-onnx-Q'
    snapshot_download(repo_id=repository, revision=revision, local_dir=MODEL_DIR,
        cache_dir=ROOT / 'data/models/huggingface',
        allow_patterns=['model_optimized.onnx', 'config.json', 'tokenizer.json',
                        'tokenizer_config.json', 'special_tokens_map.json', 'LICENSE', 'README.md'])
    hashes = {}
    for path in sorted(MODEL_DIR.iterdir()):
        if path.is_file() and path.name != 'manifest.json':
            with path.open('rb') as stream:
                hashes[path.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    if not {'model_optimized.onnx', 'tokenizer.json'} <= hashes.keys():
        raise RuntimeError('Required ONNX/tokenizer assets missing')
    manifest = {'model': 'BAAI/bge-small-en-v1.5', 'repository': repository,
                'revision': revision, 'files': hashes}
    (MODEL_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
