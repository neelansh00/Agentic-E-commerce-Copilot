"""Full-data semantic primitive checks; verification queries never enter model prompts."""
from contextlib import closing
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.ingest import connect_readonly, file_hash

ROOT = Path(__file__).resolve().parents[1]


def main():
    database = ROOT / 'data/processed/olist.sqlite'
    before = file_hash(database)
    reference = json.loads((ROOT / 'evaluation/baseline_expected.json').read_text(encoding='utf-8'))['questions']
    checks = []
    def check(name, actual, expected):
        checks.append(dict(name=name, actual=actual, expected=expected, passed=actual == expected))
    with closing(connect_readonly(database)) as db:
        scalar = lambda sql: db.execute(sql).fetchone()[0]
        check('one metric row per source order', scalar('SELECT COUNT(*) FROM metric_orders'), scalar('SELECT COUNT(*) FROM orders'))
        check('unique metric order keys', scalar('SELECT COUNT(DISTINCT order_id) FROM metric_orders'), scalar('SELECT COUNT(*) FROM metric_orders'))
        overview = reference['overview']['rows'][0]
        check('delivered payment sum vs frozen independent CSV oracle', scalar('SELECT SUM(revenue_cents) FROM metric_orders'), overview['revenue_cents'])
        check('AOV vs frozen independent CSV oracle', scalar('SELECT ROUND(AVG(revenue_cents),6) FROM metric_orders'), overview['aov_cents'])
        delivery = reference['late_delivery']['rows'][0]
        for column, expression in [('eligible_orders','SUM(delivery_eligible)'), ('late_orders','SUM(is_late)'), ('mean_delivery_days','ROUND(AVG(delivery_days),6)')]:
            check(column + ' vs frozen CSV oracle', scalar('SELECT '+expression+' FROM metric_orders'), delivery[column])
        check('ineligible delivery observations are NULL', scalar('SELECT COUNT(*) FROM metric_orders WHERE delivery_eligible=0 AND (is_late IS NOT NULL OR delivery_days IS NOT NULL)'), 0)
        check('category aggregation preserves item count', scalar('SELECT SUM(item_count) FROM metric_order_categories'), scalar('SELECT COUNT(*) FROM order_items'))
        check('seller aggregation preserves item count', scalar('SELECT SUM(item_count) FROM metric_order_sellers'), scalar('SELECT COUNT(*) FROM order_items'))
        for view in ['metric_order_categories','metric_order_sellers']:
            check(view + ' preserves item cents', scalar(f'SELECT SUM(item_sales_cents) FROM {view}'), scalar('SELECT SUM(price_cents) FROM order_items'))
            check(view + ' join does not expand its grain', scalar(f'SELECT COUNT(*) FROM {view} JOIN metric_orders USING(order_id)'), scalar(f'SELECT COUNT(*) FROM {view}'))
        check('continuous calendar including empty months', [r[0] for r in db.execute('SELECT purchase_month FROM metric_months ORDER BY purchase_month')],
              [r['purchase_month'] for r in reference['monthly_revenue']['rows']])
    check('database file unchanged', file_hash(database), before)
    report = dict(checks=checks, all_passed=all(c['passed'] for c in checks), source='Existing frozen reference was independently verified against original CSVs; join reconciliations also use raw relational tables.')
    (ROOT / 'docs/generated/phase45_metric_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"{sum(c['passed'] for c in checks)}/{len(checks)} semantic primitive checks passed")
    if not report['all_passed']:
        print(json.dumps([c for c in checks if not c['passed']],indent=2))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
