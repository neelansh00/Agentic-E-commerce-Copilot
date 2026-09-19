"""Freeze fifty explicit cases only after reference SQL matches independent CSV calculations."""
import json
from pathlib import Path
import sys
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.evaluation.benchmark import SQL_CASES, DEFINITIONS, STATISTICS, ADVERSARIAL, additional_csv_results
from app.analytics.baseline import QUERIES, query_sql
from app.analytics.reference import CsvReference
from app.evaluation.live import compare_unordered
from app.database.ingest import connect_readonly, file_hash
from scripts.run_live_evaluation import make_cases, KEYS


def main():
    output=ROOT/'evaluation/questions.json'
    if output.exists():
        raise SystemExit('Benchmark already frozen. Do not overwrite it during an experiment.')
    original,snapshot=make_cases()
    oracle=CsvReference(ROOT/'data/raw')
    additional=additional_csv_results(ROOT/'data/raw')
    cases=[]
    with closing(connect_readonly(ROOT/'data/processed/olist.sqlite')) as db:
        for case in original:
            name=case['id']; spec=QUERIES[name]
            expected=snapshot['questions'][name]['rows']
            assert not compare_unordered(oracle.result(name,spec.parameters),expected,KEYS[name]),name
            assert not compare_unordered([dict(r) for r in db.execute(query_sql(name),spec.parameters)],expected,KEYS[name]),name
            cases.append(dict(id=name,category='time_based' if name=='monthly_revenue' else 'multi_table_sql',question=case['question'],
                expected_tools=['rag','sql'] if name!='category_sales' else ['sql'],expected_status='ok',expected_tables=list(spec.tables),
                reference_sql=query_sql(name),parameters=spec.parameters,expected_rows=expected,group_keys=KEYS[name],
                interpretation=spec.interpretation,kind='sql',origin='Previously used development baseline'))
        for name,q,sql,tables,category in SQL_CASES:
            expected=additional[name]
            columns=list(expected[0]); keys=[k for k in columns if any(isinstance(r[k],str) for r in expected)]
            assert not compare_unordered([dict(r) for r in db.execute(sql)],expected,keys),name
            question=q+'\nReturn exactly these columns: '+', '.join(columns)+'. Money stays integer cents; undefined values stay NULL.'
            cases.append(dict(id=name,category=category,question=question,expected_tools=['rag','sql'] if name=='review_count' else ['sql'],
                expected_status='ok',expected_tables=tables,reference_sql=sql,parameters={},expected_rows=expected,group_keys=keys,
                interpretation='Use exactly the stated population and grain; raw record counts are not distinct entities.',kind='sql',origin='New same-author development question'))
    for name,q,heading,facts,patterns in DEFINITIONS:
        cases.append(dict(id=name,category='business_definition',question=q,expected_tools=['rag'],expected_status='ok',expected_tables=[],
                          expected_headings=[heading],interpretation='; '.join(facts),rubric_patterns=patterns,kind='definition'))
    review=oracle.result('late_reviews',{})
    stats={g['delivery_group']:g for g in review}
    expected_analysis={f'{group}_{suffix}':stats[group][column] for group in ['late','on_time'] for suffix,column in [('orders','reviewed_orders'),('mean','mean_review_score')]}
    for name,q,tools,status in STATISTICS:
        cases.append(dict(id=name,category='statistical',question=q,expected_tools=tools,expected_status=status,
                          expected_tables=['orders','reviews'] if status=='ok' else [],expected_analysis=expected_analysis if status=='ok' else {},
                          interpretation='Descriptive association only; no causal or significance claim. Reject unsupported filters and tests.',kind='statistical'))
    for name,q,tools,status,meaning in ADVERSARIAL:
        cases.append(dict(id=name,category='ambiguous_adversarial',question=q,expected_tools=tools,expected_status=status,expected_tables=[],interpretation=meaning,kind='refusal'))
    assert len(cases)==50 and len({c['id'] for c in cases})==50
    payload=dict(version=1,method='Development set: 11 prior questions, 39 newly specified cases. Explicit SQL output contracts. Not held out.',
                 database_sha256=file_hash(ROOT/'data/processed/olist.sqlite'),baseline_sha256=file_hash(ROOT/'evaluation/baseline_expected.json'),
                 knowledge_sha256=file_hash(ROOT/'knowledge_base/metrics.md'),questions=cases)
    output.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('Frozen 50 cases; all 30 reference SQL queries agree with independent CSV calculations.')


if __name__=='__main__':
    main()
