"""Read-only, allowlisted SQLite execution with bounded time and output."""
import json
import math
import sqlite3
import time
from app.database.ingest import connect_readonly
from app.text_to_sql.config import QueryLimits
from app.text_to_sql.contracts import QueryResult
from app.text_to_sql.safety import SQLITE_FUNCTIONS, validate_sql


class QueryExecutionError(ValueError):
    pass


def authorizer(allowed_tables):
    allowed = set(allowed_tables)
    def authorize(action, arg1, arg2, db_name, trigger):
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and arg1 in allowed and db_name in ('main', None):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in SQLITE_FUNCTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    return authorize


def execute_sql(database, sql, allowed_tables=None, limits: QueryLimits | None = None):
    limits = limits or QueryLimits()
    checked = validate_sql(sql, allowed_tables, limits.max_sql_chars)
    start = time.perf_counter()
    db = connect_readonly(database)
    try:
        db.execute('PRAGMA trusted_schema = OFF')
        db.execute('PRAGMA temp_store = MEMORY')
        db.execute(f'PRAGMA busy_timeout = {max(1, min(5000, int(limits.timeout_seconds * 1000)))}')
        db.enable_load_extension(False)
        # SQLite also applies this limit while reading schema/record values. A small
        # preview budget must not prevent preparing ordinary schema metadata.
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, max(4096, limits.max_result_bytes))
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, limits.max_sql_chars)
        db.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 100)
        db.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 30)
        db.set_authorizer(authorizer(checked.tables))
        deadline = start + limits.timeout_seconds
        db.set_progress_handler(lambda: int(time.perf_counter() >= deadline), 1000)
        cursor = db.execute(checked.sql)  # A single statement, never executescript.
        columns = [c[0] for c in cursor.description]
        if len(set(columns)) != len(columns):
            raise QueryExecutionError('Duplicate output column names; give each result column a unique alias')
        rows, size, truncated = [], 0, False
        for _ in range(limits.max_rows + 1):
            row = cursor.fetchone()
            if row is None:
                break
            record = dict(row)
            if any(isinstance(v, bytes) or isinstance(v, float) and not math.isfinite(v) for v in record.values()):
                raise QueryExecutionError('Binary and nonfinite results are unsupported')
            size += len(json.dumps(record, ensure_ascii=False).encode('utf-8'))
            if len(rows) >= limits.max_rows or size > limits.max_result_bytes:
                truncated = True
                break
            rows.append(record)
        return QueryResult(sql=sql, tables=list(checked.tables), columns=columns, rows=rows,
                           truncated=truncated, execution_ms=round(1000*(time.perf_counter()-start), 3))
    except sqlite3.Error as exc:
        if time.perf_counter() >= start + limits.timeout_seconds:
            raise QueryExecutionError('Query exceeded its execution time budget') from None
        raise QueryExecutionError(str(exc)[:500]) from None
    finally:
        db.close()
