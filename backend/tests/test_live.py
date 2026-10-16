import os

import pytest

from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas.extraction import Extraction, validate_evidence
from app.core.config import get_settings


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_AI") != "1", reason="Opt-in paid provider smoke test")
def test_real_provider_structured_output():
    messages = [
        {
            "id": "synthetic-m1",
            "kind": "ORIGINAL",
            "body": "The kitchen sink leaks since yesterday.",
        }
    ]
    result = OpenAIProvider(get_settings()).invoke(messages)
    extraction = Extraction.model_validate(result.data)
    validate_evidence(extraction, messages)
    assert extraction.category == "PLUMBING"
    assert extraction.room_or_area and "kitchen" in extraction.room_or_area.lower()
