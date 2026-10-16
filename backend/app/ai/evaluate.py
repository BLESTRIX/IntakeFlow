"""Explicit offline/live evaluation. Gold files are never included in model input."""

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.ai.prompts.extraction import PROMPT_VERSION
from app.ai.providers.base import MalformedOutput, TemporaryProviderError
from app.ai.providers.demo import DemoProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas.extraction import SCHEMA_VERSION, EvidenceError, Extraction, validate_evidence
from app.core.config import get_settings


def normalized(value):
    return " ".join(str(value).lower().strip(" .").split())


def evaluate(cases, provider):
    results = []
    tp = fp = fn = unsupported = predictions = evidence_ok = evidence_total = missing_tp = (
        missing_fp
    ) = missing_fn = valid = categories = 0
    settings = get_settings()
    symptom_tp = symptom_fp = symptom_fn = multiple_correct = attention_correct = 0
    costs = []
    for case in cases:
        start = time.perf_counter()
        error, parsed, result, repairs, retries, calls = None, None, None, 0, 0, 0
        while calls < settings.ai_max_calls:
            calls += 1
            try:
                result = provider.invoke(case["messages"], repair=bool(repairs))
                parsed = Extraction.model_validate(result.data)
                break
            except TemporaryProviderError:
                retries += 1
                if retries > 2:
                    error = "temporary_failure"
                    break
            except (ValidationError, MalformedOutput):
                repairs += 1
                if repairs > 1:
                    error = "malformed"
                    break
            except Exception as exc:
                error = type(exc).__name__
                break
        latency = (time.perf_counter() - start) * 1000
        output = parsed.model_dump(mode="json") if parsed else None
        cost = None
        if (
            calls == 1
            and result
            and result.input_tokens is not None
            and result.output_tokens is not None
            and settings.input_price_per_million is not None
            and settings.output_price_per_million is not None
        ):
            cost = (
                result.input_tokens * settings.input_price_per_million
                + result.output_tokens * settings.output_price_per_million
            ) / 1_000_000
            costs.append(cost)
        if parsed:
            valid += 1
            categories += parsed.category in case.get(
                "acceptable_categories", [case["expected_fields"]["category"]]
            )
            multiple_correct += parsed.multiple_issues_detected == case["multiple_issues_detected"]
            attention_correct += parsed.needs_staff_attention == case["needs_staff_attention"]
            anchors = case["symptom_anchors"]

            def matched(actual, expected):
                return normalized(expected) in normalized(actual) or normalized(
                    actual
                ) in normalized(expected)

            symptom_tp += sum(
                any(matched(actual, gold) for actual in parsed.symptoms) for gold in anchors
            )
            symptom_fn += sum(
                not any(matched(actual, gold) for actual in parsed.symptoms) for gold in anchors
            )
            symptom_fp += sum(
                not any(matched(actual, gold) for gold in anchors) for actual in parsed.symptoms
            )
            for field, gold in case["expected_fields"].items():
                if field == "category":
                    continue
                actual = output[field]
                if actual:
                    predictions += 1
                    if gold is None:
                        unsupported += 1
                        fp += 1
                    elif normalized(actual) == normalized(gold):
                        tp += 1
                    else:
                        fp += 1
                        fn += 1
                elif gold is not None:
                    fn += 1
            source = {m["id"]: m["body"] for m in case["messages"]}
            for evidence in parsed.evidence:
                evidence_total += 1
                evidence_ok += (
                    evidence.message_id in source and evidence.quote in source[evidence.message_id]
                )
            try:
                validate_evidence(parsed, case["messages"])
            except EvidenceError:
                error = "invalid_evidence"
            predicted_missing = set(parsed.missing_information)
            missing_tp += len(predicted_missing & set(case["required_missing"]))
            missing_fp += len(predicted_missing - set(case["acceptable_missing"]))
            missing_fn += len(set(case["required_missing"]) - predicted_missing)
        results.append(
            {
                "id": case["id"],
                "output": output,
                "latency_ms": round(latency, 2),
                "estimated_cost_usd": cost,
                "calls": calls,
                "error": error,
                "human_follow_up_score": None,
                "human_semantic_score": None,
            }
        )

    def ratio(a, b):
        return round(a / b, 4) if b else None

    return {
        "mode": "SIMULATED — NOT LIVE MODEL ACCURACY"
        if provider.name == "demo"
        else "LIVE MODEL — semantic human review still required",
        "provider": provider.name,
        "model": provider.model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": "maintenance-v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "count": len(cases),
        "metrics": {
            "schema_validation_success": ratio(valid, len(cases)),
            "category_accuracy": ratio(categories, len(cases)),
            "scalar_field_precision": ratio(tp, tp + fp),
            "scalar_field_recall": ratio(tp, tp + fn),
            "symptom_precision_lexical": ratio(symptom_tp, symptom_tp + symptom_fp),
            "symptom_recall_lexical": ratio(symptom_tp, symptom_tp + symptom_fn),
            "field_precision_lexical": ratio(tp + symptom_tp, tp + symptom_tp + fp + symptom_fp),
            "field_recall_lexical": ratio(tp + symptom_tp, tp + symptom_tp + fn + symptom_fn),
            "multiple_issue_flag_accuracy": ratio(multiple_correct, len(cases)),
            "attention_flag_accuracy": ratio(attention_correct, len(cases)),
            "unsupported_scalar_field_rate": ratio(unsupported, predictions),
            "evidence_reference_validity": ratio(evidence_ok, evidence_total),
            "missing_information_precision": ratio(missing_tp, missing_tp + missing_fp),
            "missing_information_recall": ratio(missing_tp, missing_tp + missing_fn),
            "follow_up_relevance": None,
            "semantic_correctness": None,
            "median_latency_ms": round(statistics.median(r["latency_ms"] for r in results), 2),
            "estimated_cost_usd": sum(costs) if len(costs) == len(cases) else None,
        },
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../evals/dataset.jsonl")
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--provider", choices=["demo", "openai"], default="demo")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--output", default="../evals/results/demo-dev.json")
    args = parser.parse_args()
    if args.provider == "openai" and not args.allow_paid:
        parser.error("Live evaluations require --allow-paid and incur provider charges")
    provider = DemoProvider() if args.provider == "demo" else OpenAIProvider(get_settings())
    cases = [
        json.loads(line) for line in Path(args.dataset).read_text().splitlines() if line.strip()
    ]
    report = evaluate([c for c in cases if c["split"] == args.split], provider)
    report["split"] = args.split
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text(
        f"# IntakeFlow evaluation\n\n{report['mode']}\n\nModel `{provider.model}` · prompt `{PROMPT_VERSION}` · schema `{SCHEMA_VERSION}` · dataset `maintenance-v1` · split `{args.split}` · {report['count']} cases.\n\n"
        + "\n".join(
            f"- {key}: {value if value is not None else 'unknown / human review pending'}"
            for key, value in report["metrics"].items()
        )
        + "\n\nScalar metrics use normalized exact matches; paraphrases require human adjudication. See rubric.md. No AI-quality conclusion follows from simulated results.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"output": str(output), "mode": report["mode"], "metrics": report["metrics"]}, indent=2
        )
    )


if __name__ == "__main__":
    main()
