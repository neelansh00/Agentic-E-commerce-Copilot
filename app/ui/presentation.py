"""Pure chart preparation: no queries, model calls, aggregation or imputation."""
import math
import re
from app.text_to_sql.evidence import CAPTIONS, DIMENSIONS


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def chart_options(result):
    if result is None or result.truncated or not 2 <= len(result.rows) <= 60:
        return None, []
    dimensions = [c for c in DIMENSIONS if c in result.columns]
    if len(dimensions) != 1:
        return None, []
    dimension = dimensions[0]
    labels = [r.get(dimension) for r in result.rows]
    if any(not isinstance(v, str) or not v for v in labels) or len(set(labels)) != len(labels):
        return None, []
    if dimension == 'purchase_month' and not all(re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', v) for v in labels):
        return None, []
    measures = [c for c in result.columns if c in CAPTIONS and c != 'boundary_month'
                and any(numeric(r.get(c)) for r in result.rows)
                and all(r.get(c) is None or numeric(r.get(c)) for r in result.rows)]
    return dimension, measures


def chart_spec(result, measure):
    dimension, measures = chart_options(result)
    if measure not in measures:
        raise ValueError('Chart requires unique groups and a supported numeric measure in a complete result.')
    rows = result.rows
    temporal = dimension == 'purchase_month'
    if temporal:
        rows = sorted(rows, key=lambda r: r[dimension])
    points, segment, previous = [], 0, None
    for row in rows:
        label, value = row[dimension], row[measure]
        if temporal:
            year, month = map(int, label.split('-'))
            current = year*12 + month
            if previous is not None and current != previous + 1:
                segment += 1
            previous = current
        if value is None:
            segment += 1
        points.append(dict(group=label, value=value/100 if value is not None and measure.endswith('_cents') else value, segment=segment))
        if value is None:
            segment += 1
    caption = CAPTIONS[measure].replace('(BRL cents)', '(BRL)')
    encoding = dict(
        x=dict(field='group', type='ordinal' if temporal else 'nominal', sort=None, title=dimension.replace('_',' ').title()),
        y=dict(field='value', type='quantitative', title=caption, scale=dict(zero=True)),
        tooltip=[dict(field='group', type='nominal'), dict(field='value',type='quantitative',title=caption)])
    if temporal:
        encoding['detail'] = dict(field='segment',type='nominal')
    return dict(data=dict(values=points), mark=dict(type='line', point=True, color='#146B59') if temporal else dict(type='bar',color='#146B59'), encoding=encoding, height=260)


def summary_metrics(response):
    if response.analysis:
        return [('Late mean review', f"{response.analysis['late_mean']:.3f}"),
                ('On-time mean review', f"{response.analysis['on_time_mean']:.3f}"),
                ('Reviewed orders', f"{response.analysis['late_orders']+response.analysis['on_time_orders']:,}")]
    result = response.result
    if result is None or result.truncated or len(result.rows) != 1:
        return []
    return [(CAPTIONS[c], str(value) if value is not None else 'Unknown')
            for c, value in result.rows[0].items() if c in CAPTIONS and (value is None or numeric(value))][:3]
