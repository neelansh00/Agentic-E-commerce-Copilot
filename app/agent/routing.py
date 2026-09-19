"""Visible routing rules. This is intent coverage, not arbitrary language understanding."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict


class Route(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tools: list[Literal['sql', 'rag', 'python']]
    operation: Literal['query', 'definition', 'late_reviews', 'clarify', 'unsupported']
    reason: str


def route_question(question):
    q = re.sub(r'\s+', ' ', question.lower()).strip().rstrip('?.!')
    def route(tools, operation, reason):
        return Route(tools=tools, operation=operation, reason=reason)
    if not q or len(question) > 4000:
        return route([], 'clarify', 'Provide a nonempty question of at most 4000 characters.')
    if re.search(r'^(please )?(drop|delete|insert|update|alter|truncate)\b|\b(drop table|delete from|insert into|alter table|truncate table|create table)\b', q):
        return route([], 'unsupported', 'This assistant provides read-only analytics.')
    if re.search(r'\b(cause|causes|caused|causal|prove|why did)\b', q):
        return route([], 'clarify', 'These observational data cannot establish causes. Ask for a descriptive comparison and specify its scope.')
    definitions = bool(re.search(r'\b(definition|defined|definitions|policy|our criteria)\b', q))
    # Only whole-question global intents are accepted for this fixed-population tool.
    # A state, seller, date or additional condition must never be silently ignored.
    stats_q = re.sub(r'^(using|according to) (our |the )?(business )?definitions?,? ', '', q)
    association = re.fullmatch(
        r'(are late deliveries associated with (lower |poor )?(customer )?(ratings|reviews|review scores)'
        r'|compare (customer )?(ratings|reviews|review scores) (for|between) late and (on-time|on time) deliveries'
        r'|is late delivery associated with (lower |poor )?(customer )?(ratings|reviews|review scores))', stats_q)
    if association:
        return route(['rag', 'sql', 'python'] if definitions else ['sql', 'python'],
                     'late_reviews', 'Compare complete review histograms at one eligible order per observation.')
    definition_only = re.fullmatch(r'(what (is|are)|explain) (the )?(revenue|aov|average order value|late delivery|cancellation rate|freight cost|payment value|poor reviews|order lifecycle)', q)
    if definition_only or re.search(r'^(what (does|is|are)|define|explain|how (is|are).*(defined|calculated))\b', q) and (
            re.search(r'\b(mean|means|definition|defined|calculated)\b', q) or
            re.match(r'^define\b', q)):
        return route(['rag'], 'definition', 'Retrieve cited business definitions without querying transactions.')
    if re.search(r'\b(associated|association|correlation|statistical|significant|test|regression|anomal|predict|forecast)\w*\b', q) or (
            'compare' in q and 'late' in q and re.search(r'review|rating', q)):
        return route([], 'unsupported', 'Currently supported Python analysis: compare review scores for all late and on-time eligible deliveries. Filtered comparisons and inferential tests are not implemented.')
    if re.search(r'\b(it|that|those|previous|above)\b', q):
        return route([], 'clarify', 'Requests are independent. Restate the metric, population and period explicitly.')
    business = definitions or bool(re.search(r'\b(revenue|aov|average order value|late|delivery|deliveries|review|rating|poor|cancellation)\w*\b', q))
    return route(['rag', 'sql'] if business else ['sql'], 'query',
                 'Retrieve metric conventions before SQL.' if business else 'Ordinary aggregation belongs in SQL.')
