"""One call budget covers transport retries, repair, and worker replay."""

import time

from pydantic import ValidationError
from sqlalchemy import func, select

from app.ai.prompts.extraction import PROMPT_VERSION
from app.ai.providers.base import ConfigurationError, MalformedOutput, TemporaryProviderError
from app.ai.providers.demo import DemoProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas.extraction import SCHEMA_VERSION, EvidenceError, Extraction, validate_evidence
from app.core.config import get_settings
from app.models import DurableJob, ModelInvocation


def configured_provider():
    settings = get_settings()
    return DemoProvider() if settings.ai_provider == "demo" else OpenAIProvider(settings)


def extract(db, job_id, messages, provider=None, sleep=time.sleep):
    settings = get_settings()
    if sum(len(m["body"]) for m in messages) > settings.ai_max_input_chars:
        raise ConfigurationError("input_limit")
    provider = provider or configured_provider()
    while True:
        job = db.scalar(select(DurableJob).where(DurableJob.id == job_id).with_for_update())
        if job.model_calls >= settings.ai_max_calls:
            db.rollback()
            raise ConfigurationError("call_budget_exhausted")
        malformed = db.scalar(
            select(func.count())
            .select_from(ModelInvocation)
            .where(ModelInvocation.job_id == job_id, ModelInvocation.error_category == "malformed")
        )
        temporary = db.scalar(
            select(func.count())
            .select_from(ModelInvocation)
            .where(ModelInvocation.job_id == job_id, ModelInvocation.error_category == "temporary")
        )
        if malformed > 1 or temporary > 2:
            db.rollback()
            raise ConfigurationError("retry_budget_exhausted")
        job.model_calls += 1
        invocation = ModelInvocation(
            org_id=job.org_id,
            request_id=job.request_id,
            job_id=job.id,
            provider=provider.name,
            model=provider.model,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            source_revision=job.source_revision,
            outcome="STARTED",
        )
        db.add(invocation)
        db.commit()  # Reserve a call before external I/O; no open transaction during inference.
        start = time.perf_counter()
        result = None
        try:
            result = provider.invoke(messages, repair=bool(malformed))
            parsed = Extraction.model_validate(result.data)
            validate_evidence(parsed, messages)
        except TemporaryProviderError:
            invocation.outcome, invocation.error_category = "FAILED", "temporary"
        except MalformedOutput as exc:
            invocation.input_tokens, invocation.output_tokens = exc.input_tokens, exc.output_tokens
            invocation.outcome, invocation.error_category = "FAILED", "malformed"
        except ValidationError:
            invocation.outcome, invocation.error_category = "FAILED", "malformed"
        except EvidenceError:
            invocation.outcome, invocation.error_category = "FAILED", "evidence"
        except ConfigurationError:
            invocation.outcome, invocation.error_category = "FAILED", "configuration"
        except Exception:
            invocation.outcome, invocation.error_category = "FAILED", "provider_error"
        else:
            invocation.outcome = "SUCCEEDED"
        invocation.latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if result:
            invocation.input_tokens, invocation.output_tokens = (
                result.input_tokens,
                result.output_tokens,
            )
        if (
            invocation.input_tokens is not None
            and invocation.output_tokens is not None
            and settings.input_price_per_million is not None
            and settings.output_price_per_million is not None
        ):
            invocation.estimated_cost = (
                invocation.input_tokens * settings.input_price_per_million
                + invocation.output_tokens * settings.output_price_per_million
            ) / 1_000_000
        db.commit()
        if invocation.outcome == "SUCCEEDED":
            return parsed, provider.name, provider.model
        category = invocation.error_category
        if category == "temporary" and temporary < 2:
            sleep(0.25 * 2**temporary)
            continue
        if category == "malformed" and malformed == 0:
            continue
        raise ConfigurationError(category)
