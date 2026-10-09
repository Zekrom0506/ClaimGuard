"""Run ClaimGuard on the 40 labelled SYNTHETIC cases and save a dated report.

Needs PostgreSQL running with the policies loaded (scripts/setup.sh does this).

Usage, from the repository root:
    python evaluation/run_evaluation.py --mode retrieval
        Search quality only. Uses the labelled facts as input, so no language
        model is called and it costs nothing.
    python evaluation/run_evaluation.py --mode full
        The whole pipeline with the real language model. Costs money
        (roughly 40 cases x 2-3 calls); never run in CI.
    Add --compare-search to also run vector-only search for comparison.
    Add --limit 5 to try a few cases first.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
# The backend is imported as a library; inside Docker it lives at /app.
sys.path.insert(0, os.environ.get("BACKEND_PATH", str(REPOSITORY_ROOT / "backend")))

import metrics  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.llm_client import LLMError, RecordingLLMClient, create_llm_client  # noqa: E402
from app.models.case import PriorAuthCase  # noqa: E402
from app.schemas.verdict import VERDICT_LABELS  # noqa: E402
from app.services.case_processor import StopProcessing, run_pipeline  # noqa: E402
from app.services.embeddings import SentenceTransformerEmbedder  # noqa: E402
from app.services.pipeline import PipelineDependencies  # noqa: E402
from app.services.retriever import retrieve_policy_chunks  # noqa: E402
from app.services.risk_model import DenialRiskModel  # noqa: E402

LABELS_FILE = REPOSITORY_ROOT / "data" / "evaluation" / "labels.json"
REPORTS_DIRECTORY = REPOSITORY_ROOT / "evaluation" / "reports"
SEARCH_MODES_TO_COMPARE = ["hybrid", "vector"]


def load_labelled_cases(limit: int | None) -> list[dict]:
    """The labelled cases, optionally only the first few."""
    labelled_cases = json.loads(LABELS_FILE.read_text())["cases"]
    if limit is not None:
        return labelled_cases[:limit]
    return labelled_cases


def labelled_fields_as_extraction(expected_fields: dict) -> dict:
    """Turn the label's correct facts into the shape the extractor produces.

    Used by retrieval mode, so search quality is measured on its own,
    without extraction mistakes mixed in.
    """
    extracted_fields = {}
    for field_name, value in expected_fields.items():
        extracted_fields[field_name] = {"value": value, "source_sentence": None}
    red_flags = []
    if expected_fields["red_flags_present"]:
        red_flags = ["documented red flag condition"]
    extracted_fields["red_flags"] = {"value": red_flags, "source_sentence": None}
    extracted_fields["other_conservative_treatments"] = {"value": [], "source_sentence": None}
    return extracted_fields


def contains_whole_value(text: str, value: str) -> bool:
    """True if value appears in text as a whole word or phrase (case-insensitive)."""
    pattern = r"(?<!\w)" + re.escape(value.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


# ---------------------------------------------------------------------------
# Retrieval mode
# ---------------------------------------------------------------------------


def evaluate_retrieval(labelled_cases: list[dict], search_mode: str, embedder) -> dict:
    """Recall@5 and MRR of the correct policy section for one search mode."""
    expected_sections = []
    retrieved_sections_per_case = []
    per_case_rows = []
    with SessionLocal() as database_session:
        for labelled_case in labelled_cases:
            retrieved_chunks = retrieve_policy_chunks(
                database_session,
                labelled_fields_as_extraction(labelled_case["expected_fields"]),
                embedder,
                search_mode=search_mode,
            )
            retrieved_sections = []
            for chunk in retrieved_chunks:
                retrieved_sections.append(chunk.section_title)
            expected_sections.append(labelled_case["expected_policy_section"])
            retrieved_sections_per_case.append(retrieved_sections)
            per_case_rows.append(
                {
                    "case_id": labelled_case["case_id"],
                    "expected_section": labelled_case["expected_policy_section"],
                    "retrieved_sections": retrieved_sections,
                }
            )

    return {
        "search_mode": search_mode,
        "recall_at_5": metrics.recall_at_k(expected_sections, retrieved_sections_per_case),
        "mean_reciprocal_rank": metrics.mean_reciprocal_rank(
            expected_sections, retrieved_sections_per_case
        ),
        "cases": per_case_rows,
    }


# ---------------------------------------------------------------------------
# Full mode
# ---------------------------------------------------------------------------


def run_one_case(labelled_case: dict, pipeline: PipelineDependencies) -> dict:
    """Run the real pipeline on one labelled PDF and collect what it produced."""
    pdf_bytes = (LABELS_FILE.parent / labelled_case["file"]).read_bytes()
    case = PriorAuthCase(original_filename=labelled_case["file"], treatment_type="lumbar_spine_mri")
    recording_client = pipeline.llm_client
    prompts_before = len(recording_client.sent_prompts)

    started_at = time.perf_counter()
    error_message = None
    with SessionLocal() as database_session:
        try:
            run_pipeline(database_session, case, pdf_bytes, pipeline)
        except StopProcessing:
            pass
        except LLMError as error:
            error_message = str(error)
    seconds = round(time.perf_counter() - started_at, 2)

    sent_text_parts = []
    for sent_prompt in recording_client.sent_prompts[prompts_before:]:
        sent_text_parts.append(sent_prompt.user_prompt)
    sent_text = "\n".join(sent_text_parts)

    leaked_fields = []
    for field_name, private_value in labelled_case["synthetic_identity"].items():
        if contains_whole_value(sent_text, private_value):
            leaked_fields.append(field_name)

    retrieved_sections = []
    for chunk_summary in case.retrieved_chunks or []:
        retrieved_sections.append(chunk_summary["section_title"])

    return {
        "case_id": labelled_case["case_id"],
        "expected_verdict": labelled_case["expected_verdict"],
        "predicted_verdict": case.verdict,
        "expected_section": labelled_case["expected_policy_section"],
        "retrieved_sections": retrieved_sections,
        "verified_citations": case.citations or [],
        "failed_citation_count": len(case.failed_citations or []),
        "extracted_fields": case.extracted_fields,
        "review_flags": case.review_flags or [],
        "denial_probability": case.denial_probability,
        "model_disagreement": case.model_disagreement,
        "leaked_identity_fields": leaked_fields,
        "seconds": seconds,
        "cost_usd": case.llm_cost_usd or 0.0,
        "error": error_message,
    }


def summarise_full_run(labelled_cases: list[dict], case_results: list[dict]) -> dict:
    """Turn per-case results into the report's headline numbers."""
    expected_verdicts = []
    predicted_verdicts = []
    expected_sections = []
    verified_citations_per_case = []
    retrieved_sections_per_case = []
    expected_fields_per_case = []
    extracted_fields_per_case = []
    total_citations = 0
    failed_citations = 0
    leak_count = 0
    seconds_per_case = []
    cost_per_case = []
    denial_probabilities = []
    disagreement_flags = []

    for labelled_case, result in zip(labelled_cases, case_results, strict=True):
        expected_verdicts.append(result["expected_verdict"])
        predicted_verdicts.append(result["predicted_verdict"])
        expected_sections.append(result["expected_section"])
        verified_citations_per_case.append(result["verified_citations"])
        retrieved_sections_per_case.append(result["retrieved_sections"])
        expected_fields_per_case.append(labelled_case["expected_fields"])
        extracted_fields_per_case.append(result["extracted_fields"])
        total_citations += len(result["verified_citations"]) + result["failed_citation_count"]
        failed_citations += result["failed_citation_count"]
        leak_count += len(result["leaked_identity_fields"])
        seconds_per_case.append(result["seconds"])
        cost_per_case.append(result["cost_usd"])
        denial_probabilities.append(result["denial_probability"])
        disagreement_flags.append(result["model_disagreement"])

    return {
        "verdict_accuracy": metrics.accuracy(expected_verdicts, predicted_verdicts),
        "confusion_matrix": metrics.confusion_matrix(
            expected_verdicts, predicted_verdicts, VERDICT_LABELS
        ),
        "citation_section_accuracy": metrics.citation_section_accuracy(
            expected_sections, verified_citations_per_case
        ),
        "retrieval_recall_at_5": metrics.recall_at_k(
            expected_sections, retrieved_sections_per_case
        ),
        "extraction_accuracy_by_field": metrics.extraction_accuracy_by_field(
            expected_fields_per_case, extracted_fields_per_case
        ),
        "hallucination_rate": metrics.hallucination_rate(total_citations, failed_citations),
        "total_citations": total_citations,
        "privacy_leaks": leak_count,
        "average_seconds_per_case": metrics.average(seconds_per_case),
        "average_cost_usd_per_case": metrics.average(cost_per_case),
        "llm_vs_risk_model": metrics.compare_llm_with_risk_model(
            expected_verdicts, predicted_verdicts, denial_probabilities, disagreement_flags
        ),
    }


def evaluate_full(labelled_cases: list[dict], search_mode: str, embedder) -> dict:
    """Run every case through the full pipeline with the real language model."""
    settings = get_settings().model_copy(update={"retrieval_search_mode": search_mode})
    pipeline = PipelineDependencies(
        settings=settings,
        llm_client=RecordingLLMClient(create_llm_client(settings)),
        embedder=embedder,
        risk_model=DenialRiskModel.load(settings.resolved_risk_model_path),
    )
    case_results = []
    for case_number, labelled_case in enumerate(labelled_cases, start=1):
        print(f"[{search_mode}] {case_number}/{len(labelled_cases)} {labelled_case['case_id']}")
        case_results.append(run_one_case(labelled_case, pipeline))

    summary = summarise_full_run(labelled_cases, case_results)
    summary["search_mode"] = search_mode
    summary["model_name"] = settings.llm_model_name
    summary["prompt_versions"] = {
        "extraction": settings.extraction_prompt_version,
        "verdict": settings.verdict_prompt_version,
    }
    summary["cases"] = case_results
    return summary


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def format_number(value: object) -> str:
    """Show ratios as percentages and leave everything else as it is."""
    if value is None:
        return "n/a"
    if isinstance(value, float) and 0.0 <= value <= 1.0:
        return f"{value * 100:.1f}%"
    return str(value)


def render_markdown(report: dict) -> str:
    """A readable summary of the report."""
    lines = [
        f"# Evaluation report {report['run_at']}",
        "",
        f"Mode: {report['mode']}. Cases: {report['case_count']} (SYNTHETIC data).",
        "",
    ]
    for run in report["runs"]:
        lines.append(f"## Search mode: {run['search_mode']}")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for metric_name, value in run.items():
            if isinstance(value, dict | list) or metric_name == "search_mode":
                continue
            lines.append(f"| {metric_name} | {format_number(value)} |")
        if "extraction_accuracy_by_field" in run:
            lines.append("")
            lines.append("| Extracted field | Accuracy |")
            lines.append("|---|---|")
            for field_name, value in run["extraction_accuracy_by_field"].items():
                lines.append(f"| {field_name} | {format_number(value)} |")
        if "llm_vs_risk_model" in run:
            lines.append("")
            lines.append("| Language model vs risk model | Value |")
            lines.append("|---|---|")
            for metric_name, value in run["llm_vs_risk_model"].items():
                lines.append(f"| {metric_name} | {format_number(value)} |")
        if "confusion_matrix" in run:
            lines.append("")
            lines.append("Confusion matrix (rows = correct answer, columns = ClaimGuard):")
            lines.append("")
            column_names = list(next(iter(run["confusion_matrix"].values())).keys())
            lines.append("| | " + " | ".join(column_names) + " |")
            lines.append("|---" * (len(column_names) + 1) + "|")
            for row_name, row in run["confusion_matrix"].items():
                counts = []
                for column_name in column_names:
                    counts.append(str(row[column_name]))
                lines.append(f"| {row_name} | " + " | ".join(counts) + " |")
        lines.append("")
    return "\n".join(lines)


def save_report(report: dict) -> Path:
    """Write <timestamp>.json and .md into evaluation/reports/ and return the JSON path."""
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_stem = f"eval_{report['mode']}_{report['run_at'].replace(':', '').replace('-', '')}"
    json_path = REPORTS_DIRECTORY / f"{file_stem}.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (REPORTS_DIRECTORY / f"{file_stem}.md").write_text(render_markdown(report), encoding="utf-8")
    return json_path


def main() -> None:
    """Parse arguments, run the chosen evaluation and save the report."""
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--mode", choices=["retrieval", "full"], default="retrieval")
    argument_parser.add_argument("--compare-search", action="store_true")
    argument_parser.add_argument("--limit", type=int, default=None)
    arguments = argument_parser.parse_args()

    labelled_cases = load_labelled_cases(arguments.limit)
    embedder = SentenceTransformerEmbedder(get_settings().embedding_model_name)
    search_modes = ["hybrid"]
    if arguments.compare_search:
        search_modes = SEARCH_MODES_TO_COMPARE

    runs = []
    for search_mode in search_modes:
        if arguments.mode == "retrieval":
            runs.append(evaluate_retrieval(labelled_cases, search_mode, embedder))
        else:
            runs.append(evaluate_full(labelled_cases, search_mode, embedder))

    report = {
        "run_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": arguments.mode,
        "case_count": len(labelled_cases),
        "data": "SYNTHETIC",
        "runs": runs,
    }
    report_path = save_report(report)
    print(render_markdown(report))
    print(f"Saved {report_path}")


if __name__ == "__main__":
    main()
