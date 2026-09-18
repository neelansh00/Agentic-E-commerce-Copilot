"""Provider secrets/configuration live here, not in prompts or logs."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ModelConfig:
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 60
    max_output_tokens: int = 3000

    @classmethod
    def from_env(cls, env_file: Path = ROOT / '.env'):
        load_dotenv(env_file, override=False)
        key = os.getenv('OPENAI_API_KEY', '').strip()
        model = os.getenv('OPENAI_MODEL', '').strip()
        if not key or not model:
            raise ValueError('Set OPENAI_API_KEY and OPENAI_MODEL in local .env. No live model is configured.')
        return cls(key, model)


@dataclass(frozen=True)
class QueryLimits:
    max_attempts: int = 3
    timeout_seconds: float = 15
    max_rows: int = 200
    max_result_bytes: int = 100_000
    max_sql_chars: int = 20_000

    def __post_init__(self):
        if not 1 <= self.max_attempts <= 3:
            raise ValueError('Use one to three SQL attempts')
        if not 0 < self.timeout_seconds <= 60 or not 1 <= self.max_rows <= 1000:
            raise ValueError('Invalid execution budget')
        if self.max_sql_chars < 1 or self.max_result_bytes < 1:
            raise ValueError('Budgets must be positive')
