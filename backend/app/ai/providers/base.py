from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResult:
    data: dict
    input_tokens: int | None = None
    output_tokens: int | None = None


class TemporaryProviderError(Exception):
    pass


class ConfigurationError(Exception):
    pass


class MalformedOutput(Exception):
    def __init__(self, message, input_tokens=None, output_tokens=None):
        super().__init__(message)
        self.input_tokens, self.output_tokens = input_tokens, output_tokens


class Provider(Protocol):
    name: str
    model: str

    def invoke(self, messages: list[dict], repair: bool = False) -> ProviderResult: ...
