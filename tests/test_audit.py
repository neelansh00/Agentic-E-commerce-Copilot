import csv
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.inspect_dataset import audit_csv, extract


class AuditTests(unittest.TestCase):
    def test_counts_csv_records_not_physical_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.csv'
            with path.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerows([['id', 'text'], ['1', 'hello\nworld'], ['2', ''], ['2', '']])
            result = audit_csv(path)
            self.assertEqual(result['rows'], 3)
            self.assertEqual(result['exact_duplicate_rows'], 1)
            self.assertEqual(result['columns']['text']['missing_count'], 2)
            self.assertEqual(result['candidate_single_column_keys'], [])

    def test_extraction_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = b'a,b\r\n1,2\r\n'
            with zipfile.ZipFile(root / 'test.zip', 'w') as archive:
                archive.writestr('table.csv', payload)
            files = extract(root / 'test.zip', root / 'raw')
            self.assertEqual(files[0].read_bytes(), payload)

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with zipfile.ZipFile(root / 'test.zip', 'w') as archive:
                archive.writestr('../outside.csv', 'id\n1\n')
            with self.assertRaisesRegex(ValueError, 'Unsafe archive path'):
                extract(root / 'test.zip', root / 'raw')
            self.assertFalse((root / 'outside.csv').exists())


if __name__ == '__main__':
    unittest.main()
