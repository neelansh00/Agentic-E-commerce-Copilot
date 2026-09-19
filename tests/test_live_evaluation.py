"""Offline tests for live-evaluation scoring; never make API requests."""
import unittest
from app.evaluation.live import RecordingModel, compare_unordered, summarize
from app.text_to_sql.contracts import SQLPlan, ModelError
from app.text_to_sql.model import ScriptedModel


class LiveEvaluationTests(unittest.TestCase):
    def test_row_order_does_not_change_group_accuracy(self):
        rows = [{'state': 'SP', 'n': 2}, {'state': 'RJ', 'n': 3}]
        self.assertEqual(compare_unordered(rows[::-1], rows, ['state']), [])

    def test_wrong_values_missing_rows_and_columns_fail(self):
        expected = [{'state': 'SP', 'n': 2}]
        for actual in [[], [{'state': 'SP', 'n': 3}], [{'state': 'SP', 'n': None}], [{'state': 'SP', 'count': 2}]]:
            with self.subTest(actual=actual):
                self.assertTrue(compare_unordered(actual, expected, ['state']))

    def test_budget_prevents_extra_calls(self):
        provider = ScriptedModel([dict(action='clarify', sql=None, message='Which month?', assumptions=[])])
        model = RecordingModel(provider, max_calls=1)
        model.generate([], SQLPlan)
        with self.assertRaisesRegex(ModelError, 'budget exhausted'):
            model.generate([], SQLPlan)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(model.calls, 1)

    def test_failed_provider_call_consumes_attempt_budget(self):
        model = RecordingModel(ScriptedModel([ModelError('Unavailable')]), max_calls=1)
        with self.assertRaises(ModelError):
            model.generate([], SQLPlan)
        self.assertEqual(model.calls, 1)
        self.assertEqual(model.outputs, [])

    def test_execution_and_answer_format_do_not_imply_result_accuracy(self):
        row = dict(executed=True, result_match=False, explanation_validated=True,
                   explanation_fallback=False, api_calls=2, response={'elapsed_ms': 10, 'usage': []})
        result = summarize([row])
        self.assertEqual(result['executed'], 1)
        self.assertEqual(result['exact_results'], 0)
        self.assertEqual(result['structurally_valid_explanations'], 1)


if __name__ == '__main__':
    unittest.main()
