"""Build the local knowledge index (download model weights separately first)."""
from pathlib import Path
import sys
import json
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.embeddings import LocalEmbedder, ROOT
from app.rag.retrieval import build_index

if __name__ == '__main__':
    start = time.perf_counter()
    metadata = build_index(LocalEmbedder())
    report = {k: metadata[k] for k in ('model', 'sources', 'dimension')}
    report.update(chunks=len(metadata['chunks']), elapsed_seconds=round(time.perf_counter()-start, 3))
    (ROOT / 'docs/generated/knowledge_index_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
