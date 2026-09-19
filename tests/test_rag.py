"""Fast, offline retrieval boundaries; synthetic vectors are not retrieval quality evidence."""
import json
from contextlib import closing
from pathlib import Path
import tempfile
import sqlite3
import unittest
from types import SimpleNamespace
from app.database.ingest import SCHEMA
from app.rag.embeddings import LocalEmbedder
from app.rag.chunks import chunk_documents
from app.rag.retrieval import build_index, Retriever, definition_answer, context_for
from app.text_to_sql.model import ScriptedModel
from app.text_to_sql.pipeline import answer_question
from app.text_to_sql.prompts import planning_messages


class FakeEmbedder:
    identity = {'model': 'synthetic-unit-test'}

    def passages(self, texts):
        return [[1, 0] if 'Revenue' in t else [0, 1] for t in texts]

    def query(self, text):
        return [[1, 0] if 'revenue' in text.lower() else [-1, 0]]


class RagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kb, self.index = self.root / 'kb', self.root / 'index'
        self.kb.mkdir()
        (self.kb / 'metrics.md').write_text('# Revenue\n\nDelivered payment value.\n\n# Reviews\n\nScores from one to five.\n')
        self.embedder = FakeEmbedder()
        build_index(self.embedder, self.kb, self.index)

    def retriever(self):
        return Retriever(self.embedder, self.kb, self.index)

    def test_chunks_preserve_exact_lines_and_stable_ids(self):
        chunks = chunk_documents(self.kb)
        self.assertEqual(chunks, chunk_documents(self.kb))
        lines = (self.kb / 'metrics.md').read_text().splitlines()
        for chunk in chunks:
            self.assertEqual(chunk.text, '\n'.join(lines[chunk.start_line-1:chunk.end_line]))
        self.assertEqual(len(chunks), 2)

    def test_chunk_bounds_and_overlap(self):
        (self.kb / 'long.md').write_text('# Long\n' + (' '.join(['word']*15)+'\n')*5)
        chunks = [c for c in chunk_documents(self.kb, max_words=30) if c.source == 'long.md']
        self.assertTrue(all(len(c.text.split()) <= 30 for c in chunks))
        self.assertEqual(chunks[0].end_line, chunks[1].start_line)

    def test_long_paragraph_rejected(self):
        (self.kb / 'long.md').write_text('word '*221)
        with self.assertRaises(ValueError):
            chunk_documents(self.kb)

    def test_cosine_ranking_and_citations(self):
        hits = self.retriever().retrieve('revenue')
        self.assertEqual(hits[0]['heading'], 'Revenue')
        self.assertEqual(hits[0]['score'], 1)
        self.assertIn('metrics.md:3-3', context_for(hits))

    def test_abstention_and_no_invented_answer(self):
        answer = definition_answer('unknown', self.retriever())
        self.assertEqual(answer['status'], 'unsupported')
        self.assertEqual(answer['sources'], [])

    def test_input_limits(self):
        for question, top_k in [('', 3), ('x'*4001, 3), ('revenue', 0), ('revenue', 11)]:
            with self.assertRaises(ValueError):
                self.retriever().retrieve(question, top_k)

    def test_stale_documents_rejected_after_loading(self):
        retriever = self.retriever()
        (self.kb / 'metrics.md').write_text('Changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            retriever.retrieve('revenue')

    def test_edit_during_build_preserves_previous_index(self):
        previous = (self.index / 'current.json').read_bytes()
        def mutate(texts):
            (self.kb / 'metrics.md').write_text('Changed while embedding')
            return [[1, 0] for _ in texts]
        self.embedder.passages = mutate
        with self.assertRaisesRegex(ValueError, 'during indexing'):
            build_index(self.embedder, self.kb, self.index)
        self.assertEqual(previous, (self.index / 'current.json').read_bytes())

    def test_corrupt_index_rejected(self):
        metadata = json.loads((self.index / 'current.json').read_text())
        (self.index / metadata['index_file']).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.retriever()

    def test_model_mismatch_rejected(self):
        self.embedder.identity = {'model': 'different'}
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            self.retriever()

    def test_dimension_mismatch_rejected(self):
        self.embedder.query = lambda text: [[1, 0, 0]]
        with self.assertRaisesRegex(ValueError, 'shape'):
            self.retriever().retrieve('revenue')

    def test_retrieved_context_replaces_full_contract(self):
        messages = planning_messages('revenue', 'orders', '', context_for(self.retriever().retrieve('revenue')))
        self.assertIn('Delivered payment value.', messages[0]['content'])
        self.assertNotIn('Seller late-delivery screen', messages[0]['content'])

    def test_pipeline_no_match_does_not_call_model(self):
        model = ScriptedModel([])
        result = answer_question('unknown', self.root / 'absent.sqlite', model, retriever=self.retriever())
        self.assertEqual(result.status, 'clarification')
        self.assertEqual(model.calls, [])

    def test_pipeline_stale_index_reports_failure(self):
        retriever = self.retriever()
        (self.kb / 'metrics.md').write_text('Changed')
        result = answer_question('revenue', self.root / 'absent.sqlite', ScriptedModel([]), retriever=retriever)
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.trace[-1]['tool'], 'business_knowledge')

    def test_sql_pipeline_receives_citations_and_keeps_query_evidence(self):
        database = self.root / 'fixture.sqlite'
        with closing(sqlite3.connect(database)) as db:
            db.executescript(SCHEMA.read_text())
        model = ScriptedModel([
            dict(action='query', sql='SELECT COUNT(*) AS n FROM orders', message='', assumptions=[]),
            dict(claims=[dict(label='Orders', row_index=0, column='n')], caveats=[]),
        ])
        result = answer_question('revenue order count', database, model, retriever=self.retriever())
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.result.rows, [{'n': 0}])
        self.assertEqual(result.sources[0]['heading'], 'Revenue')
        self.assertIn('metrics.md:3-3', model.calls[0][0]['content'])
        self.assertNotIn('Seller late-delivery screen', model.calls[0][0]['content'])

    def test_missing_model_is_explicit_without_download(self):
        with self.assertRaisesRegex(ValueError, 'Download weights first'):
            LocalEmbedder(self.root / 'missing')

    def test_token_overflow_rejected_instead_of_silent_truncation(self):
        embedder = LocalEmbedder.__new__(LocalEmbedder)
        embedder.tokenizer = SimpleNamespace(encode=lambda text: SimpleNamespace(ids=[1]*513))
        with self.assertRaisesRegex(ValueError, '512 tokens'):
            embedder.check_lengths(['long text'])


if __name__ == '__main__':
    unittest.main()
