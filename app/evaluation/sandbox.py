"""Evaluation-only engine baseline without application SQL validation.

Run against a disposable database copy. SQLite authorization, mode=ro,
query_only, a function allowlist, time and result limits remain mandatory.
"""
import json
import sqlite3
import time
from app.database.ingest import connect_readonly
from app.text_to_sql.executor import authorizer, QueryExecutionError
from app.text_to_sql.schema import TABLES
from app.text_to_sql.contracts import QueryResult


def engine_only(database, sql, timeout=30):
    start=time.perf_counter()
    db=connect_readonly(database)
    try:
        db.enable_load_extension(False)
        db.execute('PRAGMA trusted_schema=OFF')
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,20000)
        db.set_authorizer(authorizer(TABLES))
        db.set_progress_handler(lambda:int(time.perf_counter()-start>timeout),1000)
        cursor=db.execute(sql)
        columns=[c[0] for c in cursor.description]
        rows=[dict(zip(columns,r)) for r in cursor.fetchmany(201)]
        if len(set(columns))!=len(columns) or len(json.dumps(rows))>100000:
            raise QueryExecutionError('Ambiguous columns or output budget exceeded')
        return QueryResult(sql=sql,tables=[],columns=columns,rows=rows[:200],truncated=len(rows)>200,execution_ms=1000*(time.perf_counter()-start))
    except (sqlite3.Error,TypeError) as exc:
        raise QueryExecutionError(str(exc)[:300]) from None
    finally:
        db.close()
