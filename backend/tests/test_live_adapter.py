import json

import httpx

from app.ai.providers.demo import DemoProvider
from app.ai.providers.openai import OpenAIProvider
from app.core.config import Settings


def test_installed_langchain_openai_structured_output_interface():
    messages = [{"id": "m1", "kind": "ORIGINAL", "body": "The kitchen sink leaks since yesterday."}]
    output = DemoProvider().invoke(messages).data
    captured = []

    def transport(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-synthetic",
                "object": "chat.completion",
                "created": 1,
                "model": "configured-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": json.dumps(output)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )

    settings = Settings(openai_api_key="test-key-no-network", openai_model="configured-model")
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = OpenAIProvider(settings, http_client=client)
        result = provider.invoke(messages)
    assert result.data == output
    assert result.input_tokens == 100 and result.output_tokens == 50
    assert captured[0]["model"] == "configured-model"
    assert captured[0]["response_format"]["type"] == "json_schema"
    assert captured[0]["response_format"]["json_schema"]["strict"] is True
