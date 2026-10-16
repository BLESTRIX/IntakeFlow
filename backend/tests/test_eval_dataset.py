import json
from pathlib import Path

from app.ai.evaluate import evaluate
from app.ai.providers.demo import DemoProvider


def test_dataset_split_gold_evidence_and_simulation_label():
    path = Path(__file__).resolve().parents[2] / "evals/dataset.jsonl"
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(cases) >= 60
    assert len({case["id"] for case in cases}) == len(cases)
    assert len([case for case in cases if case["split"] == "dev"]) == 40
    assert len([case for case in cases if case["split"] == "heldout"]) == 24
    for case in cases:
        messages = {m["id"]: m["body"] for m in case["messages"]}
        for evidence in case["expected_evidence"]:
            assert evidence["quote"] in messages[evidence["message_id"]]
    report = evaluate([cases[0]], DemoProvider())
    assert report["mode"].startswith("SIMULATED")
    assert report["metrics"]["estimated_cost_usd"] is None
    assert report["metrics"]["follow_up_relevance"] is None
