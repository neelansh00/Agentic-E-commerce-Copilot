"""Fail-closed SQL structure validation, then SQLite authorization at execution."""
from dataclasses import dataclass
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, OptimizeError
from sqlglot.optimizer.scope import traverse_scope
from app.text_to_sql.schema import TABLES

SQLITE_FUNCTIONS = frozenset('abs avg count sum total min max round coalesce ifnull nullif lower upper length substr substring trim ltrim rtrim replace date datetime julianday strftime unixepoch cast typeof row_number rank dense_rank lag lead first_value last_value ntile percent_rank cume_dist iif if'.split())
AST_FUNCTIONS = {name.upper() for name in SQLITE_FUNCTIONS} | {
    'TIME_TO_STR', 'TS_OR_DS_TO_TIMESTAMP', 'TIME_TO_UNIX', 'UNIX_TO_TIME',
    'SUBSTRING', 'STR_POSITION', 'IF', 'DATE', 'CURRENT_DATE', 'CASE', 'AND', 'OR',
}
FORBIDDEN_NODES = frozenset('insert update delete drop alter create truncate truncatetable merge command pragma attach detach copy transaction commit rollback into lock use set grant revoke execute load export cache uncache analyze vacuum'.split())


class SQLSafetyError(ValueError):
    pass


class SchemaMismatch(SQLSafetyError):
    def __init__(self, missing):
        self.missing = sorted(missing)
        super().__init__('Query needs known tables absent from retrieved schema: ' + ', '.join(self.missing))


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    tables: tuple[str, ...]


def validate_sql(sql: str, allowed_tables=None, max_chars=20_000) -> ValidatedSQL:
    if not sql or len(sql) > max_chars or '\x00' in sql:
        raise SQLSafetyError('SQL is empty, oversized or contains a null byte')
    try:
        statements = sqlglot.parse(sql, read='sqlite')
    except (ParseError, RecursionError) as exc:
        raise SQLSafetyError('SQL parse error; return one valid SQLite SELECT') from None
    if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLSafetyError('Only one SELECT query (optionally with CTEs/set operations) is allowed')
    tree = statements[0]
    for node in tree.walk():
        if node.key in FORBIDDEN_NODES:
            raise SQLSafetyError(f'Forbidden SQL operation: {node.key}')
        if isinstance(node, exp.Func):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
            if name not in AST_FUNCTIONS:
                raise SQLSafetyError(f'Function is not allowlisted: {name}')
        if isinstance(node, exp.Table) and (node.db or node.catalog or not isinstance(node.this, exp.Identifier)):
            raise SQLSafetyError('External/qualified tables and table-valued functions are not allowed')
    physical = set()
    try:
        for scope in traverse_scope(tree):
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table):
                    physical.add(source.name.lower())
    except (OptimizeError, ValueError, RecursionError):
        raise SQLSafetyError('Unable to resolve query table scopes') from None
    if not physical:
        raise SQLSafetyError('Analytical queries must read at least one supplied business table')
    unknown = physical - TABLES
    if unknown:
        raise SQLSafetyError('Unknown or forbidden tables: ' + ', '.join(sorted(unknown)))
    if allowed_tables is not None and physical - set(allowed_tables):
        raise SchemaMismatch(physical - set(allowed_tables))
    return ValidatedSQL(sql, tuple(sorted(physical)))
