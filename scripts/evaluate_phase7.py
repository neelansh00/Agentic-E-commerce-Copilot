"""Bounded, checkpointed live benchmark and paired experiments; no production edits."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from pydantic import BaseModel, ConfigDict
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.agent.runner import run_agent
from app.database.ingest import file_hash
from app.evaluation.live import RecordingModel, compare_unordered
from app.evaluation.scoring import score_case,summarize_benchmark,rubric_score
from app.evaluation.sandbox import engine_only
from app.rag.embeddings import LocalEmbedder
from app.rag.retrieval import Retriever,context_for
from app.text_to_sql.config import ModelConfig,QueryLimits
from app.text_to_sql.model import OpenAIModel
from app.text_to_sql.contracts import SQLPlan,ModelError
from app.text_to_sql.schema import TABLES,retrieve_schema,schema_context
from app.text_to_sql.prompts import planning_messages
from app.text_to_sql.executor import execute_sql,QueryExecutionError
from app.text_to_sql.safety import SQLSafetyError
from app.text_to_sql.metric_validation import validate_metric_grain,validate_metric_result,requires_continuous_months

EXPERIMENT_IDS=['overview','monthly_revenue','state_aov','state_cancellation','category_sales','late_delivery','category_delivery','seller_performance','seller_lateness','regional_delivery']


class DefinitionResponse(BaseModel):
    model_config=ConfigDict(extra='forbid')
    answer:str


def checked_execution(database,sql,tables,question):
    validate_metric_grain(sql)
    result=execute_sql(database,sql,tables,QueryLimits(timeout_seconds=30))
    validate_metric_result(result,requires_continuous_months(question))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--section',choices=['benchmark','experiments'],required=True)
    parser.add_argument('--max-api-calls',type=int,default=150)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.live or not 1<=args.max_api_calls<=200 or args.output.exists():
        parser.error('Require --live, a fresh output path and max-api-calls in 1..200.')
    benchmark=json.loads((ROOT/'evaluation/questions.json').read_text(encoding='utf-8'))
    cases=benchmark['questions']; database=ROOT/'data/processed/olist.sqlite'
    if file_hash(database)!=benchmark['database_sha256'] or file_hash(ROOT/'knowledge_base/metrics.md')!=benchmark['knowledge_sha256']:
        parser.error('Data or metric contract changed since benchmark freeze.')
    model=RecordingModel(OpenAIModel(ModelConfig.from_env()),args.max_api_calls)
    retriever=Retriever(LocalEmbedder())
    report=dict(section=args.section,started_at=datetime.now(timezone.utc).isoformat(),model=model.name,complete=False,
                benchmark_sha256=file_hash(ROOT/'evaluation/questions.json'),database_sha256=file_hash(database),
                results=[],experiments=[],max_api_calls=args.max_api_calls,
                source_hashes={str(p.relative_to(ROOT)):file_hash(p) for folder in ['app/agent','app/text_to_sql','app/rag','app/evaluation'] for p in (ROOT/folder).glob('*.py')})
    def save():
        report['api_calls']=model.calls
        report['usage']=model.usage
        if report['results']:
            report['summary']=summarize_benchmark(report['results'])
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        if args.section=='benchmark':
            for case in cases:
                if model.calls>=args.max_api_calls:
                    raise ModelError('API call budget exhausted')
                before=model.calls; first=len(model.outputs)
                response=run_agent(case['question'],database,model,retriever,QueryLimits(timeout_seconds=30))
                report['results'].append(dict(id=case['id'],category=case['category'],score=score_case(case,response),
                    response=response.model_dump(),api_calls=model.calls-before,model_outputs=model.outputs[first:]))
                save()
                print(f"{case['id']}: {response.status}; correct={report['results'][-1]['score']['result_correct']}",flush=True)
                if any('Model request failed' in t.get('error','') or 'budget exhausted' in t.get('error','') for t in response.trace):
                    raise ModelError('Provider/budget failure; stopped without repeated calls.')
            report['complete']=len(report['results'])==50
        else:
            with tempfile.TemporaryDirectory(prefix='olist_eval_') as directory:
                isolated=Path(directory)/'readonly.sqlite'
                shutil.copyfile(database,isolated)
                copy_hash=file_hash(isolated)
                for identifier in EXPERIMENT_IDS:
                    case=next(c for c in cases if c['id']==identifier)
                    table_subset,_=retrieve_schema(case['question'])
                    context=schema_context(database,table_subset)
                    aware=None
                    for mode,tables in [('full_schema',sorted(TABLES)),('retrieved_schema',table_subset)]:
                        start=time.perf_counter(); before=model.calls; usage_start=len(model.usage)
                        supplied_schema=schema_context(database,tables)
                        plan=model.generate(planning_messages(case['question'],supplied_schema,''),SQLPlan)
                        record=dict(experiment='A',id=identifier,mode=mode,plan=plan.model_dump(),executed=False,correct=False)
                        try:
                            if plan.action!='query' or not plan.sql:
                                raise SQLSafetyError('Planner did not produce a query')
                            result=checked_execution(database,plan.sql,tables,case['question'])
                            record.update(executed=True,correct=not result.truncated and not compare_unordered(result.rows,case['expected_rows'],case['group_keys']),result=result.model_dump())
                        except (SQLSafetyError,QueryExecutionError) as exc:
                            record['error']=str(exc)
                        record.update(latency_ms=1000*(time.perf_counter()-start),api_calls=model.calls-before,usage=model.usage[usage_start:],schema_characters=len(supplied_schema))
                        report['experiments'].append(record); save()
                        if mode=='retrieved_schema': aware=record
                    # B uses the EXACT same retrieved-schema initial plan in both arms.
                    base=dict(experiment='B',id=identifier,mode='no_application_validation_no_retry',executed=False,correct=False,api_calls=0,plan=aware['plan'])
                    start=time.perf_counter()
                    try:
                        if aware['plan']['action']!='query' or not aware['plan']['sql']:
                            raise QueryExecutionError('Planner did not produce a query')
                        result=engine_only(isolated,aware['plan']['sql'])
                        base.update(executed=True,correct=not result.truncated and not compare_unordered(result.rows,case['expected_rows'],case['group_keys']),result=result.model_dump())
                    except QueryExecutionError as exc:
                        base['error']=str(exc)
                    base['execution_latency_ms']=1000*(time.perf_counter()-start)
                    report['experiments'].append(base)
                    guarded=dict(aware,experiment='B',mode='validation_and_retry',attempts=[aware['plan']],initial_plan_reused=True)
                    before=model.calls; repair_start=time.perf_counter()
                    for attempt in range(2,4):
                        if guarded['executed']: break
                        feedback=f"Previous SQL: {guarded['plan']['sql']}\n{guarded.get('error','No query')}"
                        plan=model.generate(planning_messages(case['question'],context,feedback),SQLPlan)
                        guarded['attempts'].append(plan.model_dump()); guarded['plan']=plan.model_dump()
                        try:
                            if plan.action!='query' or not plan.sql: raise SQLSafetyError('Planner did not produce a query')
                            result=checked_execution(database,plan.sql,table_subset,case['question'])
                            guarded.update(executed=True,correct=not result.truncated and not compare_unordered(result.rows,case['expected_rows'],case['group_keys']),result=result.model_dump())
                        except (SQLSafetyError,QueryExecutionError) as exc:
                            guarded['error']=str(exc)
                    guarded['additional_api_calls']=model.calls-before
                    guarded['additional_repair_ms']=1000*(time.perf_counter()-repair_start)
                    guarded['initial_generation_and_validation_ms']=guarded.pop('latency_ms')
                    report['experiments'].append(guarded); save()
                    print(f"A/B {identifier}: full={report['experiments'][-4]['correct']} retrieved={aware['correct']} engine={base['correct']} repaired={guarded['correct']}",flush=True)
                report['isolated_copy_unchanged']=copy_hash==file_hash(isolated)
            for case in [c for c in cases if c['kind']=='definition']:
                for mode in ['without_definitions','with_rag']:
                    sources=retriever.retrieve_for_sql(case['question']) if mode=='with_rag' else []
                    messages=[dict(role='system',content='Explain the requested metric for this e-commerce project concisely. Use provided project context if available. Do not invent a project policy; say when it is unknown. Context:\n'+context_for(sources)),dict(role='user',content=case['question'])]
                    start=time.perf_counter()
                    answer=model.generate(messages,DefinitionResponse)
                    report['experiments'].append(dict(experiment='C',id=case['id'],mode=mode,answer=answer.answer,sources=sources,rubric=rubric_score(answer.answer,case['rubric_patterns']),latency_ms=1000*(time.perf_counter()-start)))
                    save()
                print(f"C {case['id']} completed",flush=True)
            report['complete']=len(report['experiments'])==56
    except ModelError as exc:
        report['stop_reason']=str(exc)
    finally:
        report['database_unchanged']=file_hash(database)==report['database_sha256']
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps(report.get('summary',dict(complete=report['complete'],api_calls=model.calls)),indent=2))
    if not report['complete'] or not report['database_unchanged']: raise SystemExit(1)


if __name__=='__main__': main()
