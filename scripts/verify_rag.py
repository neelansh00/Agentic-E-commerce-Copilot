"""Measure real local retrieval, separately from scripted SQL and LLM accuracy."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.embeddings import ROOT, LocalEmbedder
from app.rag.retrieval import Retriever
from app.analytics.reporting import write_project_metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['dev', 'test', 'all'], default='all')
    args = parser.parse_args()
    start = time.perf_counter()
    retriever = Retriever(LocalEmbedder())
    startup = time.perf_counter()-start
    cases = json.loads((ROOT / 'evaluation/rag_questions.json').read_text())
    rows = []
    for case in cases:
        if args.split != 'all' and case['split'] != args.split:
            continue
        start = time.perf_counter()
        hits = retriever.retrieve(case['question'])
        elapsed = (time.perf_counter()-start)*1000
        headings = [h['heading'] for h in hits]
        expected = case['expected_heading']
        rank = headings.index(expected)+1 if expected in headings else None
        row = dict(case, headings=headings, scores=[h['score'] for h in hits], rank=rank,
                   top1_correct=headings[:1] == [expected] if expected else not hits,
                   passed=rank is not None if expected else not hits, elapsed_ms=round(elapsed, 3))
        rows.append(row)
        print(f"{case['id']} {'PASS' if row['passed'] else 'MISS'} {row['scores']} {headings}")
    groups = {}
    for split in sorted({r['split'] for r in rows}):
        group = [r for r in rows if r['split'] == split]
        supported = [r for r in group if r['expected_heading']]
        unknown = [r for r in group if not r['expected_heading']]
        groups[split] = dict(questions=len(group), supported=len(supported), unknown=len(unknown),
            hit_at_3=sum(r['passed'] for r in supported)/len(supported),
            top1_accuracy=sum(r['top1_correct'] for r in supported)/len(supported),
            mrr_at_3=sum(1/r['rank'] if r['rank'] else 0 for r in supported)/len(supported),
            abstention_accuracy=sum(r['passed'] for r in unknown)/len(unknown),
            median_query_ms=round(statistics.median(r['elapsed_ms'] for r in group), 3))
    report = dict(mode='Real local embeddings; no LLM/API calls', threshold=retriever.threshold,
                  top_k=3, startup_seconds=round(startup, 3), groups=groups, results=rows,
                  chunks=len(retriever.metadata['chunks']),
                  model=retriever.metadata['model'], sources=retriever.metadata['sources'])
    output = ROOT / 'docs/generated'
    name = 'rag_report' if args.split == 'all' else 'rag_' + args.split
    (output / (name+'.json')).write_text(json.dumps(report, indent=2)+'\n')
    lines = ['# Phase 4 local retrieval evaluation', '', report['mode']+'.', '',
             f"{report['chunks']} chunks, top-k 3, cosine threshold {retriever.threshold}. Startup {startup:.3f}s; query latency excludes startup.", '',
             '| Split | Supported / unknown | Hit@3 | Top-1 | MRR@3 | Unknown abstention | Median ms |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for split, g in groups.items():
        lines.append(f"| {split} | {g['supported']} / {g['unknown']} | {g['hit_at_3']:.1%} | {g['top1_accuracy']:.1%} | {g['mrr_at_3']:.3f} | {g['abstention_accuracy']:.1%} | {g['median_query_ms']} |")
    lines += ['', 'Cases were manually written before running retrieval. Threshold 0.60 was chosen before development evaluation; test cases were not used to tune it. This small same-author benchmark is not an independent production test. Hit@3 measures whether the expected heading is returned, not completeness of all required definitions or answer correctness. Similarity is not a probability. Unknown cases are easy unrelated topics; business-adjacent unsupported requests can still retrieve related excerpts.', '',
              'Definition responses copy source text; SQL planning with retrieved context is tested using scripted responses only. No generative RAG improvement, causal claim or LLM accuracy is established.', '', '## Failures', '']
    lines += [f"- {r['id']}: {r['question']} — retrieved {r['headings']}" for r in rows if not r['passed']] or ['None on this run.']
    lines += ['', '## Ranking misses', '']
    lines += [f"- {r['id']}: expected {r['expected_heading']} at rank {r['rank']}; first result was {r['headings'][:1]}." for r in rows if r['expected_heading'] and not r['top1_correct']] or ['None on this run.']
    (output / (name+'.md')).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    if args.split == 'all':
        write_project_metrics(ROOT)


if __name__ == '__main__':
    main()
