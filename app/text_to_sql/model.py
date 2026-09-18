"""Small replaceable model interface; scripted provider is explicitly offline."""
from typing import Protocol
from pydantic import BaseModel, ValidationError
from app.text_to_sql.config import ModelConfig
from app.text_to_sql.contracts import ModelError


class Model(Protocol):
    name: str
    usage: list[dict]

    def generate(self, messages: list[dict], output_type: type[BaseModel]) -> BaseModel: ...


class OpenAIModel:
    def __init__(self, config: ModelConfig, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=config.api_key, timeout=config.timeout_seconds, max_retries=0)
        self.client, self.config = client, config
        self.name = config.model
        self.usage = []

    def generate(self, messages, output_type):
        # Never send DB rows for planning. Explanation receives only bounded query results.
        try:
            response = self.client.responses.parse(model=self.name, input=messages,
                text_format=output_type, max_output_tokens=self.config.max_output_tokens, store=False)
            if response.usage is not None:
                self.usage.append(response.usage.model_dump())
            if response.status != 'completed' or response.output_parsed is None:
                raise ModelError('Model refused, returned incomplete output, or produced no structured result.')
            return output_type.model_validate(response.output_parsed)
        except ModelError:
            raise
        except Exception as exc:
            # Do not echo request bodies, credentials or provider exception details.
            raise ModelError(f'Model request failed ({type(exc).__name__}). Check credentials, model access and connectivity.') from None


class ScriptedModel:
    """Replay explicit responses to exercise plumbing; never reported as LLM accuracy."""
    name = 'offline-scripted-not-an-llm'

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.usage = []

    def generate(self, messages, output_type):
        self.calls.append(messages)
        try:
            response = next(self.responses)
            if isinstance(response, Exception):
                raise response
            return output_type.model_validate(response)
        except (StopIteration, ValidationError) as exc:
            raise ModelError(f'Scripted response failure ({type(exc).__name__})') from None
