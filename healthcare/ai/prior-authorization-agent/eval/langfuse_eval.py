"""planv4 D4 — turn the labeled set into a Langfuse dataset and run the agent system as a
Langfuse experiment, so the accuracy / fairness / reliability / cost dashboards update each run.

    ./.venv/bin/python -m eval.langfuse_eval --upload     # (re)create the dataset
    ./.venv/bin/python -m eval.langfuse_eval --run NAME   # run an experiment over it

Requires LANGFUSE_ENABLED=true + keys in .env (self-hosted docker or cloud). The per-case
scores (decision_correct, schema_first_try, hallucination_flag, escalated, approved) and the
demographic tags are attached by src/observability during run_case; this script links each
trace to a dataset item + run so the runs are comparable over time."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.models import PatientCase
from src.graph import run_case
from src import observability as obs

DATASET = "pa-cases"
TESTS = Path(__file__).resolve().parent / "test_cases.json"


def upload() -> None:
    client = obs.get_client()
    if not client:
        raise SystemExit("Langfuse disabled — set LANGFUSE_ENABLED=true + keys in .env")
    cases = json.loads(TESTS.read_text())
    client.create_dataset(name=DATASET, description="Labeled prior-auth eval set (planv4).")
    for tc in cases:
        client.create_dataset_item(
            dataset_name=DATASET, id=tc["id"],
            input=tc["case"], expected_output=tc["expected_label"],
        )
    client.flush()
    print(f"Uploaded {len(cases)} items to dataset '{DATASET}'.")


def _label(final) -> str:
    if not final.get("needs_pa"):
        return "AUTO_CLEAR"
    if not final.get("coverage_ok"):
        return "NOT_COVERED"
    d = final.get("decision")
    return d.outcome.value if d else "NEEDS_INFO"


def _task(*, item, **_):
    """Run the agent system on one dataset item; the return is the predicted label.
    run_case still attaches the per-step trace + reliability/hallucination scores."""
    final = run_case(PatientCase(**item.input), expected_label=item.expected_output)
    return _label(final)


def _correct(*, output, expected_output, **_):
    """Item-level evaluator: decision correctness vs the labeled expectation."""
    return {"name": "decision_correct", "value": 1 if output == expected_output else 0}


def run(run_name: str, concurrency: int = 1) -> None:
    client = obs.get_client()
    if not client:
        raise SystemExit("Langfuse disabled — set LANGFUSE_ENABLED=true + keys in .env")
    dataset = client.get_dataset(DATASET)
    # concurrency=1 by default: the per-case STATS snapshot in the tracer isn't thread-safe.
    result = client.run_experiment(
        name=run_name, data=list(dataset.items), task=_task,
        evaluators=[_correct], max_concurrency=concurrency,
    )
    client.flush()
    print(f"Experiment '{run_name}' completed over {len(list(dataset.items))} items. "
          "See the Langfuse dashboards / dataset runs.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true", help="create/refresh the dataset")
    ap.add_argument("--run", metavar="NAME", help="run an experiment with this name")
    ap.add_argument("--concurrency", type=int, default=1, help="parallel cases (1 = safe)")
    args = ap.parse_args()
    if args.upload:
        upload()
    if args.run:
        run(args.run, concurrency=args.concurrency)
    if not (args.upload or args.run):
        ap.print_help()


if __name__ == "__main__":
    main()
