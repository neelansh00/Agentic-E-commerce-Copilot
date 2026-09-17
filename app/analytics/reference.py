"""Independent ground-truth implementation over original CSVs, without SQL.

This intentionally duplicates metric logic for verification: it must not read SQL
results or reuse the database's order_facts transformation as an oracle.
"""
import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 6) if values else None


def percentage(numerator, denominator):
    return round(100 * numerator / denominator, 6) if denominator else None


def optional_sum(values):
    values = [v for v in values if v is not None]
    return sum(values) if values else None


def group_by(values, key):
    groups = defaultdict(list)
    for value in values:
        groups[key(value)].append(value)
    return groups


def descending_nullable(value):
    return (value is None, -value if value is not None else 0)


def category_sort(value):
    return (value is not None, value or '')  # SQLite ascending NULL first.


class CsvReference:
    def __init__(self, raw_dir: Path):
        self.raw_dir = Path(raw_dir)
        self.customers = {r['customer_id']: r for r in self.read('olist_customers_dataset.csv')}
        self.products = {r['product_id']: r for r in self.read('olist_products_dataset.csv')}
        self.translations = {r['product_category_name']: r['product_category_name_english']
                             for r in self.read('product_category_name_translation.csv')}
        self.orders = {r['order_id']: r for r in self.read('olist_orders_dataset.csv')}
        payments = defaultdict(int)
        for row in self.read('olist_order_payments_dataset.csv'):
            payments[row['order_id']] += int(Decimal(row['payment_value']) * 100)
        reviews = {}
        for r in self.read('olist_order_reviews_dataset.csv'):
            order = self.orders[r['order_id']]
            if r['review_creation_date'] < order['order_purchase_timestamp'] or r['review_answer_timestamp'] < r['review_creation_date']:
                continue
            key = (r['review_answer_timestamp'], r['review_creation_date'], r['review_id'])
            previous = reviews.get(r['order_id'])
            if previous is None or key > previous[0]:
                reviews[r['order_id']] = (key, int(r['review_score']))
        for identifier, order in self.orders.items():
            order['paid'] = payments.get(identifier)
            order['score'] = reviews[identifier][1] if identifier in reviews else None
            order['state'] = self.customers[order['customer_id']]['customer_state']
            order['successful'] = order['order_status'] == 'delivered'
            purchase, delivered, estimated = (order[c] for c in
                ('order_purchase_timestamp', 'order_delivered_customer_date', 'order_estimated_delivery_date'))
            order['eligible'] = bool(order['successful'] and delivered and estimated and delivered >= purchase)
            order['late'] = bool(order['eligible'] and delivered > estimated)
            order['days'] = (datetime.fromisoformat(delivered) - datetime.fromisoformat(purchase)).total_seconds() / 86400 if order['eligible'] else None
        self.items = list(self.read('olist_order_items_dataset.csv'))
        self.seller_orders = defaultdict(dict)
        self.category_orders = defaultdict(set)
        for item in self.items:
            oid = item['order_id']
            seller = self.seller_orders[item['seller_id']]
            seller[oid] = seller.get(oid, 0) + int(Decimal(item['price']) * 100)
            category = self.products[item['product_id']]['product_category_name'] or None
            self.category_orders[category].add(oid)

    def read(self, filename):
        with (self.raw_dir / filename).open(encoding='utf-8-sig', newline='') as stream:
            yield from csv.DictReader(stream)

    def label(self, category):
        return self.translations.get(category, category if category is not None else 'Unknown')

    def result(self, name, parameters):
        orders = list(self.orders.values())
        successful = [o for o in orders if o['successful']]
        eligible = [o for o in orders if o['eligible']]
        if name == 'overview':
            canceled = sum(o['order_status'] == 'canceled' for o in orders)
            paid = [o['paid'] for o in successful if o['paid'] is not None]
            return [dict(total_orders=len(orders), unique_buyers=len({self.customers[o['customer_id']]['customer_unique_id'] for o in orders}),
                         delivered_orders=len(successful), paid_delivered_orders=len(paid),
                         delivered_missing_payment=len(successful) - len(paid), revenue_cents=optional_sum(paid),
                         aov_cents=mean(paid), canceled_orders=canceled, cancellation_pct=percentage(canceled, len(orders)))]
        if name == 'state_cancellation':
            output = []
            for state, group in group_by(orders, lambda o: o['state']).items():
                canceled = sum(o['order_status'] == 'canceled' for o in group)
                output.append(dict(customer_state=state, total_orders=len(group), canceled_orders=canceled, cancellation_pct=percentage(canceled, len(group))))
            return sorted(output, key=lambda r: (-r['cancellation_pct'], -r['total_orders'], r['customer_state']))
        if name == 'state_aov':
            output = []
            for state, group in group_by(successful, lambda o: o['state']).items():
                paid = [o['paid'] for o in group if o['paid'] is not None]
                output.append(dict(customer_state=state, delivered_orders=len(group), paid_delivered_orders=len(paid),
                                   delivered_missing_payment=len(group) - len(paid), revenue_cents=optional_sum(paid), aov_cents=mean(paid)))
            return sorted(output, key=lambda r: (descending_nullable(r['aov_cents']), r['customer_state']))
        if name == 'monthly_revenue':
            if not orders:
                return []
            groups = group_by(orders, lambda o: o['order_purchase_timestamp'][:7])
            first, last = min(groups), max(groups)
            current, output = first, []
            while current <= last:
                group = groups.get(current, [])
                delivered = [o for o in group if o['successful']]
                paid = [o['paid'] for o in delivered if o['paid'] is not None]
                output.append(dict(purchase_month=current, boundary_month=int(current in (first, last)), total_orders=len(group),
                                   delivered_orders=len(delivered), paid_delivered_orders=len(paid), delivered_missing_payment=len(delivered)-len(paid),
                                   revenue_cents=optional_sum(paid), aov_cents=mean(paid)))
                year, month = map(int, current.split('-'))
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
                current = f'{year:04}-{month:02}'
            return output
        if name == 'category_sales':
            output = []
            items = [i for i in self.items if self.orders[i['order_id']]['successful']]
            for category, group in group_by(items, lambda i: self.products[i['product_id']]['product_category_name'] or None).items():
                output.append(dict(category_key=category, category_label=self.label(category), item_count=len(group),
                                   delivered_orders=len({i['order_id'] for i in group}),
                                   item_sales_cents=sum(int(Decimal(i['price']) * 100) for i in group),
                                   freight_cents=sum(int(Decimal(i['freight_value']) * 100) for i in group)))
            return sorted(output, key=lambda r: (-r['item_sales_cents'], category_sort(r['category_key'])))[:parameters['top_n']]
        if name == 'late_delivery':
            late = sum(o['late'] for o in eligible)
            return [dict(delivered_orders=len(successful), eligible_orders=len(eligible), excluded_orders=len(successful)-len(eligible),
                         late_orders=late, late_pct=percentage(late, len(eligible)), mean_delivery_days=mean(o['days'] for o in eligible),
                         calendar_day_late_orders=sum(o['order_delivered_customer_date'][:10] > o['order_estimated_delivery_date'][:10] for o in eligible))]
        if name == 'late_reviews':
            output = []
            for late, group in group_by(eligible, lambda o: o['late']).items():
                scores = [o['score'] for o in group if o['score'] is not None]
                poor = sum(s <= 2 for s in scores)
                output.append(dict(delivery_group='late' if late else 'on_time', eligible_orders=len(group), reviewed_orders=len(scores),
                                   missing_eligible_review=len(group)-len(scores), mean_review_score=mean(scores), poor_review_orders=poor,
                                   poor_review_pct=percentage(poor, len(scores))))
            return sorted(output, key=lambda r: r['delivery_group'])
        if name == 'regional_delivery':
            output = []
            for state, group in group_by(orders, lambda o: o['state']).items():
                observed = [o for o in group if o['eligible']]
                late = sum(o['late'] for o in observed)
                output.append(dict(customer_state=state, total_orders=len(group), eligible_orders=len(observed), late_orders=late,
                                   late_pct=percentage(late, len(observed)), mean_delivery_days=mean(o['days'] for o in observed)))
            return sorted(output, key=lambda r: (-r['total_orders'], r['customer_state']))
        if name == 'category_delivery':
            output = []
            for category, identifiers in self.category_orders.items():
                observed = [self.orders[oid] for oid in identifiers if self.orders[oid]['eligible']]
                if len(observed) < parameters['min_orders']:
                    continue
                late = sum(o['late'] for o in observed)
                output.append(dict(category_key=category, category_label=self.label(category), eligible_orders=len(observed), late_orders=late,
                                   late_pct=percentage(late, len(observed)), mean_delivery_days=mean(o['days'] for o in observed)))
            return sorted(output, key=lambda r: (-r['mean_delivery_days'], category_sort(r['category_key'])))[:parameters['top_n']]
        if name == 'seller_performance':
            scores = [o['score'] for o in successful if o['score'] is not None]
            platform_mean = sum(scores) / len(scores) if scores else None
            output = []
            for seller, order_sales in self.seller_orders.items():
                delivered = [self.orders[oid] for oid in order_sales if self.orders[oid]['successful']]
                seller_scores = [o['score'] for o in delivered if o['score'] is not None]
                if len(seller_scores) < parameters['min_reviewed_orders'] or platform_mean is None:
                    continue
                seller_mean = sum(seller_scores) / len(seller_scores)
                if seller_mean >= platform_mean:
                    continue
                output.append(dict(seller_id=seller, delivered_orders=len(delivered), reviewed_orders=len(seller_scores),
                                   item_sales_cents=sum(order_sales[o['order_id']] for o in delivered), mean_review_score=round(seller_mean, 6),
                                   platform_mean_review_score=round(platform_mean, 6)))
            return sorted(output, key=lambda r: (-r['item_sales_cents'], r['seller_id']))[:parameters['top_n']]
        if name == 'seller_lateness':
            platform_rate = sum(o['late'] for o in eligible)/len(eligible) if eligible else None
            output = []
            for seller, order_sales in self.seller_orders.items():
                observed = [self.orders[oid] for oid in order_sales if self.orders[oid]['eligible']]
                if len(observed) < parameters['min_orders'] or platform_rate is None:
                    continue
                late = sum(o['late'] for o in observed)
                if late / len(observed) <= platform_rate:
                    continue
                output.append(dict(seller_id=seller, eligible_orders=len(observed), late_orders=late,
                                   late_pct=percentage(late, len(observed)), platform_late_pct=round(100 * platform_rate, 6)))
            return sorted(output, key=lambda r: (-r['late_pct'], -r['eligible_orders'], r['seller_id']))[:parameters['top_n']]
        raise ValueError(f'Unknown reference: {name}')


def compare_rows(actual, expected, tolerance=0.000002):
    """Exact row order/keys/integers/nulls; absolute tolerance for rounded float metrics."""
    errors = []
    if len(actual) != len(expected):
        errors.append(f'Row count: SQL={len(actual)}, CSV reference={len(expected)}')
    for index, (sql_row, csv_row) in enumerate(zip(actual, expected)):
        if sql_row.keys() != csv_row.keys():
            errors.append(f'Row {index}: column keys differ')
            continue
        for column, truth in csv_row.items():
            observed = sql_row[column]
            if isinstance(truth, float):
                equal = isinstance(observed, (float, int)) and abs(observed - truth) <= tolerance
            else:
                equal = observed == truth
            if not equal:
                errors.append(f'Row {index}, {column}: SQL={observed!r}, CSV={truth!r}')
    return errors
