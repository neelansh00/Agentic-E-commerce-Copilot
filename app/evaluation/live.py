"""Strict result comparison and bounded live-call accounting."""
import json
from app.analytics.reference import compare_rows
from app.text_to_sql.contracts import ModelError


def compare_unordered(actual, expected, keys=()):
    # Group identity fixes row alignment; presentation ordering is not scored.
    def identity(row):
        return json.dumps([row.get(k) for k in keys], ensure_ascii=False)
    return compare_rows(sorted(actual, key=identity), sorted(expected, key=identity))


class RecordingModel:
    def __init__(self, model, max_calls=88):
        self.model, self.name, self.usage = model, model.name, model.usage
        self.max_calls, self.calls, self.outputs = max_calls, 0, []

    def generate(self, messages, output_type):
        if self.calls >= self.max_calls:
            raise ModelError('Live evaluation API call budget exhausted')
        self.calls += 1
        value = self.model.generate(messages, output_type)
        self.outputs.append({'type': output_type.__name__, 'value': value.model_dump()})
        return value


def summarize(rows):
    if not rows:
        return {}
    import statistics
    usage = [u for r in rows for u in r['response']['usage']]
    return dict(questions=len(rows), executed=sum(r['executed'] for r in rows),
        exact_results=sum(r['result_match'] for r in rows),
        structurally_valid_explanations=sum(r['explanation_validated'] for r in rows),
        explanation_fallbacks=sum(r['explanation_fallback'] for r in rows),
        api_calls=sum(r['api_calls'] for r in rows),
        input_tokens=sum(u['input_tokens'] for u in usage),
        cached_input_tokens=sum(u.get('input_tokens_details', {}).get('cached_tokens', 0) for u in usage),
        output_tokens=sum(u['output_tokens'] for u in usage),
        median_latency_ms=round(statistics.median(r['response']['elapsed_ms'] for r in rows), 3))
