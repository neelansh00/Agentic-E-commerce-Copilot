"""Exact cosine search; JSON metadata and checksummed FAISS data, no pickle."""
import hashlib
import json
from pathlib import Path
import uuid
import faiss
import numpy as np
from app.rag.chunks import chunk_documents, source_hashes, CHUNK_VERSION
from app.rag.embeddings import ROOT

KNOWLEDGE = ROOT / 'knowledge_base'
INDEX = ROOT / 'data/processed/knowledge_index'


def normalized(values):
    array = np.asarray(values, dtype='float32')
    if array.ndim != 2 or not np.isfinite(array).all() or (np.linalg.norm(array, axis=1) == 0).any():
        raise ValueError('Invalid embedding vectors')
    array = np.ascontiguousarray(array)
    faiss.normalize_L2(array)
    return array


def build_index(embedder, knowledge=KNOWLEDGE, directory=INDEX):
    hashes = source_hashes(knowledge)
    chunks = chunk_documents(knowledge)
    vectors = normalized(embedder.passages([c.heading + '\n' + c.text for c in chunks]))
    if source_hashes(knowledge) != hashes:
        raise ValueError('Knowledge documents changed during indexing; rebuild')
    if len(vectors) != len(chunks):
        raise ValueError('Embedding count mismatch')
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + '.faiss'
    faiss.write_index(index, str(directory / name))
    metadata = {'version': CHUNK_VERSION, 'model': embedder.identity, 'sources': hashes,
                'chunks': [c.to_dict() for c in chunks], 'dimension': index.d, 'index_file': name,
                'sha256': hashlib.sha256((directory / name).read_bytes()).hexdigest()}
    temporary = directory / (uuid.uuid4().hex + '.json')
    temporary.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    temporary.replace(directory / 'current.json')
    return metadata


class Retriever:
    def __init__(self, embedder, knowledge=KNOWLEDGE, directory=INDEX, threshold=0.60):
        if not -1 <= threshold <= 1:
            raise ValueError('Invalid similarity threshold')
        self.embedder, self.knowledge, self.threshold = embedder, Path(knowledge), threshold
        directory = Path(directory)
        self.metadata = json.loads((directory / 'current.json').read_text(encoding='utf-8'))
        m = self.metadata
        if m['version'] != CHUNK_VERSION or m['model'] != embedder.identity:
            raise ValueError('Index/model incompatible; rebuild the knowledge index')
        self.check_sources()
        if Path(m['index_file']).name != m['index_file']:
            raise ValueError('Invalid index path')
        data = (directory / m['index_file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != m['sha256']:
            raise ValueError('Index checksum mismatch; rebuild')
        self.index = faiss.deserialize_index(np.frombuffer(data, dtype='uint8'))
        if self.index.d != m['dimension'] or self.index.ntotal != len(m['chunks']):
            raise ValueError('Index shape mismatch')

    def check_sources(self):
        if self.metadata['sources'] != source_hashes(self.knowledge):
            raise ValueError('Knowledge documents changed; rebuild the knowledge index')

    def retrieve(self, question, top_k=3):
        if not question.strip() or len(question) > 4000 or not 1 <= top_k <= 10:
            raise ValueError('Use a nonempty question up to 4000 characters and top_k 1–10')
        self.check_sources()
        query = normalized(self.embedder.query(question))
        if query.shape != (1, self.index.d):
            raise ValueError('Query embedding shape mismatch')
        scores, ids = self.index.search(query, min(top_k, self.index.ntotal))
        return [dict(self.metadata['chunks'][int(i)], score=round(float(score), 6))
                for score, i in zip(scores[0], ids[0]) if i >= 0 and score >= self.threshold]


def context_for(hits):
    return '\n\n'.join(f"[{h['source']}:{h['start_line']}-{h['end_line']} | {h['heading']}]\n{h['text']}" for h in hits)


def definition_answer(question, retriever):
    hits = retriever.retrieve(question)
    return {'status': 'ok' if hits else 'unsupported', 'sources': hits,
            'answer': context_for(hits) if hits else 'No sufficiently relevant business definition was found. Please clarify the metric.',
            'mode': 'Local semantic retrieval with verbatim excerpts; no LLM synthesis',
            'trace': [{'tool': 'business_knowledge', 'returned_chunks': len(hits)}]}
