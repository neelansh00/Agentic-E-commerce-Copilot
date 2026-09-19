"""Phase 3 CLI. Offline demos replay fixed responses; --live explicitly enables API use."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.text_to_sql.config import ModelConfig
from app.text_to_sql.model import OpenAIModel, ScriptedModel
from app.text_to_sql.pipeline import answer_question

DEMOS = {
    'count': ('How many orders are there?', 'SELECT COUNT(*) AS total_orders FROM orders', 'total_orders', 'Total orders'),
    'cancellation': ('What is the cancellation rate?', "SELECT COUNT(*) total_orders, SUM(CASE WHEN order_status='canceled' THEN 1 ELSE 0 END) canceled_orders, ROUND(100.0 * SUM(CASE WHEN order_status='canceled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0),6) cancellation_pct FROM orders", 'cancellation_pct', 'Cancellation percentage'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--demo', choices=DEMOS)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--define', help='Retrieve cited business definitions locally')
    parser.add_argument('--rag', action='store_true', help='Use retrieved definitions in SQL planning')
    parser.add_argument('--question')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/processed/olist.sqlite')
    parser.add_argument('--json', action='store_true', help='Show SQL, data, schema selection, trace and execution information')
    args = parser.parse_args()
    retriever = None
    if args.rag or args.define:
        from app.rag.embeddings import LocalEmbedder
        from app.rag.retrieval import Retriever, definition_answer
        try:
            retriever = Retriever(LocalEmbedder())
            if args.define:
                if args.question:
                    parser.error('--define already contains the question')
                response = definition_answer(args.define, retriever)
                print(json.dumps(response, indent=2) if args.json else response['answer'])
                return
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
    if args.demo:
        if args.question:
            parser.error('--demo replays a fixed example; use --live --question for natural-language generation')
        question, sql, column, label = DEMOS[args.demo]
        model = ScriptedModel([dict(action='query', sql=sql, message='', assumptions=[]),
                              dict(claims=[dict(label=label, row_index=0, column=column)], caveats=['descriptive_only'])])
    else:
        if not args.question:
            parser.error('--live requires --question')
        question = args.question
        try:
            model = OpenAIModel(ModelConfig.from_env())
        except ValueError as exc:
            parser.error(str(exc))
    result = answer_question(question, args.database, model, retriever=retriever)
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Mode: {model.name}\nQuestion: {question}\nStatus: {result.status}\n{result.answer}')
        for caveat in result.caveats:
            print(caveat)
        print('Use --json to inspect SQL, data, tool trace and timing.')
    if result.status == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
