"""Phase 5 CLI: explicit live SQL or genuinely local definition/statistical tools."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.agent.routing import route_question
from app.agent.runner import run_agent
from app.text_to_sql.config import ModelConfig
from app.text_to_sql.model import OpenAIModel, ScriptedModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true', help='Authorize model API calls for SQL generation')
    mode.add_argument('--demo-count', action='store_true', help='Replay only the fixed total-orders example')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/processed/olist.sqlite')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    route = route_question(args.question)
    model, retriever = None, None
    try:
        if args.demo_count:
            if args.question != 'How many orders are there?':
                parser.error('--demo-count requires the exact question: How many orders are there?')
            model = ScriptedModel([
                dict(action='query', sql='SELECT COUNT(*) AS total_orders FROM orders', message='', assumptions=[]),
                dict(claims=[dict(label='Order count', row_index=0, column='total_orders')], caveats=['descriptive_only'])])
        elif args.live and route.operation == 'query':
            model = OpenAIModel(ModelConfig.from_env())
        if 'rag' in route.tools:
            from app.rag.embeddings import LocalEmbedder
            from app.rag.retrieval import Retriever
            retriever = Retriever(LocalEmbedder())
        response = run_agent(args.question, args.database, model, retriever)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    if args.json:
        print(response.model_dump_json(indent=2))
    else:
        print(f'Status: {response.status}\nTools: {", ".join(response.route.tools)}\n{response.answer}')
        for caveat in response.caveats:
            print(caveat)
        print('Use --json for SQL, data, sources, tool trace, usage and timing.')
    if response.status == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
