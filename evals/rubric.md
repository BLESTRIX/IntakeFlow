# Evaluation protocol — maintenance-v1

The fixed corpus contains 40 development cases and 24 held-out cases. `scripts/build_eval_dataset.py` is the readable gold-label source; the checked-in JSONL is the evaluation input. Gold labels and rubric text are never passed to the provider. Freeze prompt, schema and model before opening held-out results. Any subsequent tuning requires a new held-out dataset version.

Automatic scoring uses normalized exact scalar matches, allowed category labels, exact authorized evidence substrings, required missing-field recall and acceptable missing-label precision. A populated scalar whose gold value is null contributes to unsupported-scalar rate. These metrics do not establish semantic truth; paraphrases can lower exact-match recall. Missing denominators are unknown. Costs require known tokens and configured prices. Simulated and live results are explicitly separate.

Apply this human rubric to every returned question set and extraction, using the original conversation and gold evidence. Do not use another LLM as the sole judge.

| Score | Follow-up-question relevance |
| --- | --- |
| 2 | At most three questions; all address missing actionable facts or separation of unrelated issues, without assuming unsupported facts. If nothing useful is missing, an empty set is appropriate. |
| 1 | At least one useful question, but includes an already-answered detail, redundant wording or a low-value question. |
| 0 | Unrelated, fabricated, leading, unsafe, asks for approval/dispatch, ignores required location/symptoms, or fails to request necessary issue separation. |

Semantic correctness score 2: faithful fields/summary, no invented details, uncertainty and contradictions preserved, appropriate category and multiple-issue flags. Score 1: a limited omission/over-specific inference requiring correction. Score 0: fabricated actionable facts, contradiction silently resolved, wrong issue/category or unauthorized action. Compare paraphrases to gold anchors rather than demanding identical prose. Independently inspect symptoms and reported impact; quote validity alone is insufficient. A second reviewer should adjudicate disagreements, documenting case IDs and reasons.

The JSON report contains per-case output plus null human scores. Fill a CSV with columns `id,follow_up_relevance,semantic_correctness,notes`, integer scores 0–2, then import:

```text
uv run python -m app.ai.review_evaluation ../evals/results/live-heldout.json reviewer-scores.csv
```

The importer validates IDs and score ranges, retains notes, and adds normalized mean scores (mean/2) to a new `*-reviewed.json` and Markdown report. It rejects missing or duplicate scores. This is the documented way to measure human metrics, rather than fabricating them when no person has reviewed a run.

Staff-correction corpus cases also include before/after staff drafts. The model's responsibility is proposing an extraction; correction preservation is a deterministic application invariant covered by PostgreSQL workflow tests, not a model-accuracy metric. Contradictory and multi-issue cases warrant manual adjudication of null/primary-field choices. Preserve raw machine results alongside adjudicated scores.
