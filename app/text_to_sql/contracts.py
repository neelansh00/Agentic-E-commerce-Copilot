"""Typed boundaries between the model, executor, and final response."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SQLPlan(StrictModel):
    action: Literal['query', 'clarify', 'unsupported']
    sql: str | None
    message: str
    assumptions: list[str]


class EvidenceClaim(StrictModel):
    # The model chooses a label and evidence location, never supplies its own value.
    label: str
    row_index: int
    column: str


class Explanation(StrictModel):
    claims: list[EvidenceClaim]
    caveats: list[str]


class QueryResult(StrictModel):
    sql: str
    tables: list[str]
    columns: list[str]
    rows: list[dict]
    truncated: bool
    execution_ms: float


class PipelineResult(StrictModel):
    status: Literal['ok', 'clarification', 'unsupported', 'failed']
    answer: str
    observations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    schema_tables: list[str] = Field(default_factory=list)
    schema_reasons: dict[str, str] = Field(default_factory=dict)
    result: QueryResult | None = None
    trace: list[dict] = Field(default_factory=list)
    usage: list[dict] = Field(default_factory=list)
    elapsed_ms: float = 0
    model: str


class ModelError(Exception):
    """Sanitized provider/structured-output failure, safe to display."""
