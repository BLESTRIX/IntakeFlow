import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("scores")
    args = parser.parse_args()
    source = Path(args.report)
    report = json.loads(source.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(Path(args.scores).open(encoding="utf-8", newline="")))
    scores = {row["id"]: row for row in rows}
    if len(scores) != len(rows) or set(scores) != {r["id"] for r in report["results"]}:
        parser.error("Provide exactly one score row per report case ID")
    for result in report["results"]:
        row = scores[result["id"]]
        for field in ["follow_up_relevance", "semantic_correctness"]:
            try:
                score = int(row[field])
            except (KeyError, ValueError):
                parser.error("Scores must be integers from 0 to 2")
            if score not in {0, 1, 2}:
                parser.error("Scores must be integers from 0 to 2")
            result["human_" + field] = score
        result["reviewer_notes"] = row.get("notes", "")
    for field in ["follow_up_relevance", "semantic_correctness"]:
        report["metrics"][field] = sum(r["human_" + field] for r in report["results"]) / (
            2 * len(report["results"])
        )
    output = source.with_stem(source.stem + "-reviewed")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text(
        f"# Reviewed evaluation\n\n{report['mode']}\n\n"
        + "\n".join(f"- {key}: {value}" for key, value in report["metrics"].items())
        + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
