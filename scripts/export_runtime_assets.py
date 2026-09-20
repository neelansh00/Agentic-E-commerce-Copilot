"""Export only prepared runtime assets. No CSVs, credentials, source code or caches."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.deployment import digest, allowed, MAX_BYTES
from app.rag.embeddings import LocalEmbedder, MODEL_DIR
from app.rag.retrieval import Retriever, INDEX


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/runtime-assets.zip')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output file; existing bundles are preserved.')
    retriever = Retriever(LocalEmbedder())  # Verify hashes/model/knowledge before export.
    manifest = retriever.embedder.identity
    files = [ROOT / 'data/processed/olist.sqlite', INDEX / 'current.json',
             INDEX / retriever.metadata['index_file'], MODEL_DIR / 'manifest.json',
             *(MODEL_DIR / name for name in manifest['files'])]
    if sum(p.stat().st_size for p in files) > MAX_BYTES:
        raise ValueError('Runtime assets exceed deployment size limit.')
    before = {p: digest(p) for p in files}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                name = path.relative_to(ROOT / 'data').as_posix()
                if not allowed(name):
                    raise ValueError('Unexpected asset path')
                bundle.write(path, name)
        if any(digest(p) != value for p, value in before.items()):
            raise ValueError('Assets changed during export; retry after stopping rebuilds.')
    except Exception:
        args.output.unlink(missing_ok=True)
        raise
    print(json.dumps(dict(file=str(args.output), sha256=digest(args.output),
                          bytes=args.output.stat().st_size, files=len(files)), indent=2))


if __name__ == '__main__':
    main()
