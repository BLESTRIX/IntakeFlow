import json

import openai
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.ai.prompts.extraction import SYSTEM_PROMPT
from app.ai.providers.base import (
    ConfigurationError,
    MalformedOutput,
    ProviderResult,
    TemporaryProviderError,
)
from app.ai.schemas.extraction import Extraction


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings, http_client=None):
        if not settings.openai_api_key or not settings.openai_model:
            raise ConfigurationError("Set OPENAI_API_KEY and OPENAI_MODEL")
        self.model = settings.openai_model
        # Disable SDK retries: the service owns one bounded retry/call budget.
        model = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=self.model,
            timeout=settings.ai_timeout_seconds,
            max_retries=0,
            max_tokens=settings.ai_max_output_tokens,
            http_client=http_client,
        )
        self.structured = model.with_structured_output(
            Extraction, method="json_schema", strict=True, include_raw=True
        )

    def invoke(self, messages, repair=False):
        instruction = SYSTEM_PROMPT + (
            "\nPrevious output failed schema validation. Produce the exact schema from the same sources."
            if repair
            else ""
        )
        try:
            result = self.structured.invoke(
                [
                    SystemMessage(content=instruction),
                    HumanMessage(content=json.dumps({"authorized_messages": messages})),
                ]
            )
        except (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        ) as exc:
            raise TemporaryProviderError(type(exc).__name__) from exc
        except (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.BadRequestError,
            openai.NotFoundError,
        ) as exc:
            raise ConfigurationError(type(exc).__name__) from exc
        raw = result.get("raw")
        usage = getattr(raw, "usage_metadata", None) or {}
        parsed = result.get("parsed")
        if parsed is None or result.get("parsing_error"):
            raise MalformedOutput(
                "Structured output was malformed or refused",
                usage.get("input_tokens"),
                usage.get("output_tokens"),
            )
        return ProviderResult(
            parsed.model_dump(mode="json"), usage.get("input_tokens"), usage.get("output_tokens")
        )
