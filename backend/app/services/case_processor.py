"""The background job that turns an uploaded PDF into a checked case."""

import logging
import time
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.llm_client import LLMError, LLMResponse, calculate_cost_usd
from app.models.case import CaseStatus, PriorAuthCase
from app.services.extractor import extract_case_fields
from app.services.pdf_reader import PdfReadError, read_pdf_text
from app.services.pipeline import PipelineDependencies
from app.services.privacy_masker import mask_private_information
from app.services.prompt_safety import looks_like_prompt_injection
from app.services.retriever import RetrievedChunk, retrieve_policy_chunks
from app.services.verdict import FLAG_NO_VALID_CITATIONS, generate_verdict

logger = logging.getLogger(__name__)


class StopProcessing(Exception):
    """A step decided the case needs a human before anything else runs."""


def set_status(database_session: Session, case: PriorAuthCase, status: str) -> None:
    """Change the case status and save it right away so the frontend sees progress."""
    case.status = status
    database_session.commit()


def add_review_flag(case: PriorAuthCase, flag: str) -> None:
    """Add a reason for a human to look closer.

    A new list is assigned (not appended in place) so SQLAlchemy notices the change.
    """
    existing_flags = list(case.review_flags or [])
    if flag not in existing_flags:
        existing_flags.append(flag)
    case.review_flags = existing_flags


def record_llm_usage(
    case: PriorAuthCase, responses: list[LLMResponse], pipeline: PipelineDependencies
) -> None:
    """Add the tokens and estimated cost of these model calls to the case."""
    for response in responses:
        case.llm_model_name = response.model_name
        case.llm_input_tokens = (case.llm_input_tokens or 0) + response.input_tokens
        case.llm_output_tokens = (case.llm_output_tokens or 0) + response.output_tokens
    case.llm_cost_usd = calculate_cost_usd(
        case.llm_input_tokens or 0, case.llm_output_tokens or 0, pipeline.settings
    )


def record_prompt_version(case: PriorAuthCase, task_name: str, version: str) -> None:
    """Remember which prompt version produced this case's results."""
    prompt_versions = dict(case.prompt_versions or {})
    prompt_versions[task_name] = version
    case.prompt_versions = prompt_versions


def read_and_mask(case: PriorAuthCase, pdf_bytes: bytes) -> None:
    """Step 1 and 2: read the PDF, then hide private details."""
    case.original_text = read_pdf_text(pdf_bytes)
    masking_result = mask_private_information(case.original_text)
    case.masked_text = masking_result.masked_text
    case.pii_values = masking_result.pii_values

    # The document is still processed; the flag makes sure a human reads it carefully.
    if looks_like_prompt_injection(case.masked_text):
        add_review_flag(case, "possible_prompt_injection")


def extract_fields(case: PriorAuthCase, pipeline: PipelineDependencies) -> None:
    """Step 3: structured extraction from the MASKED text only."""
    prompt_version = pipeline.settings.extraction_prompt_version
    outcome = extract_case_fields(case.masked_text or "", pipeline.llm_client, prompt_version)
    record_llm_usage(case, outcome.responses, pipeline)
    record_prompt_version(case, "extraction", prompt_version)

    if not outcome.succeeded:
        add_review_flag(case, "extraction_invalid")
        raise StopProcessing()

    case.extracted_fields = outcome.fields.model_dump()
    for field_name in outcome.unverified_source_fields:
        add_review_flag(case, f"extraction_source_not_found:{field_name}")


def retrieve_policy(
    database_session: Session, case: PriorAuthCase, pipeline: PipelineDependencies
) -> list[RetrievedChunk]:
    """Step 4: find the policy chunks that apply to this case."""
    retrieved_chunks = retrieve_policy_chunks(
        database_session,
        case.extracted_fields or {},
        pipeline.embedder,
        search_mode=pipeline.settings.retrieval_search_mode,
        treatment_type=case.treatment_type,
    )
    if not retrieved_chunks:
        add_review_flag(case, "no_policy_found")
        raise StopProcessing()

    chunk_summaries = []
    for chunk in retrieved_chunks:
        chunk_summaries.append(
            {
                "chunk_id": chunk.chunk_id,
                "policy_name": chunk.policy_name,
                "section_title": chunk.section_title,
                "page_number": chunk.page_number,
                "fused_score": chunk.fused_score,
            }
        )
    case.retrieved_chunks = chunk_summaries
    return retrieved_chunks


def decide_verdict(
    case: PriorAuthCase, retrieved_chunks: list[RetrievedChunk], pipeline: PipelineDependencies
) -> None:
    """Step 5: the verdict with citations, checked in code."""
    prompt_version = pipeline.settings.verdict_prompt_version
    outcome = generate_verdict(
        case.extracted_fields or {},
        case.masked_text or "",
        retrieved_chunks,
        pipeline.llm_client,
        prompt_version,
    )
    record_llm_usage(case, outcome.responses, pipeline)
    record_prompt_version(case, "verdict", prompt_version)
    for flag in outcome.flags:
        add_review_flag(case, flag)
    if outcome.answer is None:
        raise StopProcessing()

    case.verdict = outcome.answer.verdict
    case.verdict_reason = outcome.answer.reason
    requirement_checks = []
    for requirement in outcome.answer.requirements:
        requirement_checks.append(requirement.model_dump())
    case.requirement_checks = requirement_checks
    case.citations = [asdict(citation) for citation in outcome.verified_citations]
    case.failed_citations = [asdict(citation) for citation in outcome.failed_citations]

    if FLAG_NO_VALID_CITATIONS in outcome.flags:
        # A verdict without any checkable evidence is not shown as a normal result.
        raise StopProcessing()


def run_pipeline(
    database_session: Session,
    case: PriorAuthCase,
    pdf_bytes: bytes,
    pipeline: PipelineDependencies,
) -> None:
    """Run every step in order, saving after each one."""
    read_and_mask(case, pdf_bytes)
    database_session.commit()

    extract_fields(case, pipeline)
    database_session.commit()

    retrieved_chunks = retrieve_policy(database_session, case, pipeline)
    database_session.commit()

    decide_verdict(case, retrieved_chunks, pipeline)
    database_session.commit()


def process_case(case_id: str, pdf_bytes: bytes, pipeline: PipelineDependencies) -> None:
    """Process one case from start to finish. Runs after the upload response is sent.

    Opens its own database session because the request's session is closed
    by the time a background task runs.
    """
    database_session = SessionLocal()
    started_at = time.perf_counter()
    try:
        case = database_session.get(PriorAuthCase, case_id)
        if case is None:
            logger.error("Case %s not found for processing", case_id)
            return

        set_status(database_session, case, CaseStatus.PROCESSING)
        try:
            run_pipeline(database_session, case, pdf_bytes, pipeline)
            final_status = CaseStatus.DONE
        except StopProcessing:
            final_status = CaseStatus.NEEDS_HUMAN_REVIEW
        except PdfReadError as error:
            case.error_message = str(error)
            final_status = CaseStatus.FAILED
        except LLMError as error:
            logger.error("Language model unavailable for case %s: %s", case_id, error)
            case.error_message = "The language model could not be reached."
            final_status = CaseStatus.FAILED
        except Exception:
            # Log the case id only: an error message could contain document text.
            logger.exception("Processing failed for case %s", case_id)
            database_session.rollback()
            case.error_message = "Processing failed. Please try again."
            final_status = CaseStatus.FAILED

        case.processing_seconds = round(time.perf_counter() - started_at, 2)
        set_status(database_session, case, final_status)
        logger.info("Case %s finished with status %s", case_id, final_status)
    finally:
        database_session.close()
