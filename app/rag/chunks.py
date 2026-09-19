"""Heading-aware, bounded Markdown chunks with exact source line references."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re

CHUNK_VERSION = 'heading-lines-v1'


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    heading: str
    start_line: int
    end_line: int
    text: str

    def to_dict(self):
        return asdict(self)


def source_hashes(directory):
    return {p.name: hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
            for p in sorted(Path(directory).glob('*.md'))}


def chunk_documents(directory: Path, max_words=220, overlap_lines=1):
    if max_words < 30 or overlap_lines < 0:
        raise ValueError('Invalid chunk size/overlap')
    output = []
    for path in sorted(Path(directory).glob('*.md')):
        lines = path.read_text(encoding='utf-8').splitlines()
        sections, heading, start = [], path.stem, 0
        for index, line in enumerate(lines):
            if re.match(r'^#{1,6} ', line):
                if index > start:
                    sections.append((heading, start, index))
                heading, start = line.lstrip('#').strip(), index + 1
        if start < len(lines):
            sections.append((heading, start, len(lines)))
        for heading, first, last in sections:
            first_content = first
            while first_content < last:
                while first_content < last and not lines[first_content].strip():
                    first_content += 1
                if first_content >= last:
                    break
                end, words = first_content, 0
                while end < last:
                    length = len(lines[end].split())
                    if end > first_content and words + length > max_words:
                        break
                    if length > max_words:
                        raise ValueError(f'{path.name}:{end+1}: paragraph exceeds {max_words} words; split the Markdown paragraph')
                    words += length
                    end += 1
                trimmed_end = end
                while trimmed_end > first_content and not lines[trimmed_end-1].strip():
                    trimmed_end -= 1
                text = '\n'.join(lines[first_content:trimmed_end])
                identity = f'{path.name}:{heading}:{first_content+1}:{trimmed_end}:{text}'
                output.append(Chunk(hashlib.sha256(identity.encode()).hexdigest()[:16], path.name,
                                    heading, first_content+1, trimmed_end, text))
                if end >= last:
                    break
                first_content = max(first_content + 1, end - overlap_lines)
    if not output:
        raise ValueError('No Markdown knowledge documents found')
    return output
