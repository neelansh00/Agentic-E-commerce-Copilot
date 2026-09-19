"""Explicit local model assets: inference never downloads weights or calls an API."""
import hashlib
import json
from pathlib import Path
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / 'data/models/bge-small-en-v1.5'
REVISION = '52398278842ec682c6f32300af41344b1c0b0bb2'


class LocalEmbedder:
    def __init__(self, directory=MODEL_DIR):
        directory = Path(directory)
        if not (directory / 'manifest.json').exists():
            raise ValueError('Download weights first: python scripts/download_embedding_model.py')
        manifest = json.loads((directory / 'manifest.json').read_text())
        if manifest['revision'] != REVISION or manifest['model'] != 'BAAI/bge-small-en-v1.5':
            raise ValueError('Embedding model revision mismatch')
        required = {'model_optimized.onnx', 'tokenizer.json', 'config.json', 'tokenizer_config.json', 'special_tokens_map.json'}
        if not required <= manifest['files'].keys():
            raise ValueError('Incomplete embedding assets')
        for name, expected in manifest['files'].items():
            if Path(name).name != name:
                raise ValueError('Invalid model asset path')
            with (directory / name).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('Embedding asset checksum mismatch: ' + name)
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.identity = dict(manifest, fastembed=version('fastembed'))
        self.model = TextEmbedding(model_name=manifest['model'], specific_model_path=str(directory),
                                   local_files_only=True, providers=['CPUExecutionProvider'], cuda=False, threads=2)

    def passages(self, texts):
        texts = list(texts)
        self.check_lengths(texts)
        return list(self.model.passage_embed(texts))

    def query(self, text):
        self.check_lengths([text])
        return list(self.model.query_embed(text))

    def check_lengths(self, texts):
        if any(len(self.tokenizer.encode(text).ids) > 512 for text in texts):
            raise ValueError('Embedding input exceeds 512 tokens; shorten the question or split the source paragraph')
