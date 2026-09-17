"""Rebuild the SQLite database from audited source CSVs."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database.ingest import load_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'data/raw')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/processed/olist.sqlite')
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/generated/load_report.json')
    args = parser.parse_args()
    report = load_database(args.raw_dir, args.database)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
