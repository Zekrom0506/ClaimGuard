"""Find the policy chunks that apply to a case (the "R" in RAG).

Two searches run side by side:

- Vector search compares meanings. "Patient has not tried physiotherapy" is
  close to "no conservative therapy" even though the words differ.
- Keyword search (PostgreSQL full-text) matches exact words. Embeddings are
  weak on codes such as "M54.16" or "72148": to the model they are just
  strings of characters, but the keyword index matches them exactly.

Reciprocal Rank Fusion then merges the two ranked lists into one.
"""

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.policy_chunk import PolicyChunk
from app.services.embeddings import Embedder

CANDIDATES_PER_SEARCH = 20
DEFAULT_TOP_K = 5
# Standard RRF constant from the original paper. It stops the very top ranks
# from completely dominating: rank 1 scores 1/61, rank 2 scores 1/62, ...
RRF_K = 60

SEARCH_MODE_HYBRID = "hybrid"
SEARCH_MODE_VECTOR = "vector"


@dataclass
class RetrievedChunk:
    """A policy chunk returned by the search, with how it ranked."""

    chunk_id: int
    policy_name: str
    section_title: str
    page_number: int
    text: str
    fused_score: float
    vector_rank: int | None
    keyword_rank: int | None


def build_case_summary(extracted_fields: dict) -> str:
    """Describe the case in plain sentences for vector search.

    Built from the extracted (already masked) fields, never the raw document.
    """
    sentences = ["Lumbar spine MRI prior authorization request."]

    procedure_code = extracted_fields["procedure_code"]["value"]
    if procedure_code:
        sentences.append(f"CPT code {procedure_code}.")

    diagnosis_codes = extracted_fields["diagnosis_codes"]["value"]
    if diagnosis_codes:
        sentences.append(f"Diagnosis codes {', '.join(diagnosis_codes)}.")

    symptom_weeks = extracted_fields["symptom_duration_weeks"]["value"]
    if symptom_weeks is None:
        sentences.append("Duration of symptoms is not documented.")
    else:
        sentences.append(f"Low back pain for {symptom_weeks:g} weeks.")

    therapy_weeks = extracted_fields["physical_therapy_weeks"]["value"]
    if therapy_weeks is None:
        sentences.append("Length of conservative therapy is not documented.")
    elif therapy_weeks == 0:
        sentences.append("No physical therapy or conservative therapy has been tried.")
    else:
        sentences.append(f"Completed {therapy_weeks:g} weeks of physical therapy.")

    red_flags = extracted_fields["red_flags"]["value"]
    if red_flags:
        sentences.append(f"Red flag conditions: {'; '.join(red_flags)}.")
    else:
        sentences.append("No red flag conditions.")

    if extracted_fields["prior_lumbar_mri_within_12_months"]["value"]:
        sentences.append("Repeat imaging: lumbar MRI within the last twelve months.")
    if extracted_fields["neurological_exam_documented"]["value"] is False:
        sentences.append("Neurological examination findings are not documented.")

    return " ".join(sentences)


def build_keyword_terms(extracted_fields: dict) -> list[str]:
    """Words and codes worth matching exactly."""
    keyword_terms = ["lumbar", "MRI"]
    procedure_code = extracted_fields["procedure_code"]["value"]
    if procedure_code:
        keyword_terms.append(procedure_code)
    keyword_terms.extend(extracted_fields["diagnosis_codes"]["value"])

    if extracted_fields["red_flags"]["value"]:
        keyword_terms.extend(["red", "flag"])
    if extracted_fields["prior_lumbar_mri_within_12_months"]["value"]:
        keyword_terms.extend(["repeat", "previous"])
    if extracted_fields["physical_therapy_weeks"]["value"] in (None, 0):
        keyword_terms.extend(["conservative", "therapy"])

    has_unknown_fact = (
        extracted_fields["symptom_duration_weeks"]["value"] is None
        or extracted_fields["physical_therapy_weeks"]["value"] is None
        or extracted_fields["neurological_exam_documented"]["value"] is False
    )
    if has_unknown_fact:
        keyword_terms.extend(["documentation", "requirements"])
    return keyword_terms


def build_tsquery(keyword_terms: list[str]) -> str:
    """Join terms with OR for to_tsquery, dropping characters it would choke on.

    OR (|) instead of AND (&): a chunk should rank well if it matches many terms,
    but it should not be excluded for missing one.
    """
    safe_terms = []
    for term in keyword_terms:
        for word in term.split():
            cleaned_word = re.sub(r"[^A-Za-z0-9.]", "", word).strip(".")
            if cleaned_word and cleaned_word not in safe_terms:
                safe_terms.append(cleaned_word)
    return " | ".join(safe_terms)


def vector_search(
    database_session: Session, query_vector: list[float], treatment_type: str, limit: int
) -> list[int]:
    """Chunk ids ordered from most to least similar in meaning."""
    statement = (
        select(PolicyChunk.id)
        .where(PolicyChunk.treatment_type == treatment_type)
        .order_by(PolicyChunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    return list(database_session.scalars(statement))


def keyword_search(
    database_session: Session, tsquery_text: str, treatment_type: str, limit: int
) -> list[int]:
    """Chunk ids that contain the keywords, best match first."""
    if tsquery_text == "":
        return []
    query = func.to_tsquery("english", tsquery_text)
    statement = (
        select(PolicyChunk.id)
        .where(PolicyChunk.treatment_type == treatment_type)
        .where(PolicyChunk.search_vector.op("@@")(query))
        .order_by(func.ts_rank_cd(PolicyChunk.search_vector, query).desc())
        .limit(limit)
    )
    return list(database_session.scalars(statement))


def reciprocal_rank_fusion(ranked_id_lists: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Merge ranked lists: each list gives an item 1 / (k + rank), and scores are added.

    Only ranks are used, never raw scores, so it does not matter that cosine
    distance and ts_rank are on completely different scales. An item ranked
    well by both searches beats an item ranked first by only one.
    """
    fused_scores: dict[int, float] = {}
    for ranked_ids in ranked_id_lists:
        for position, item_id in enumerate(ranked_ids):
            rank = position + 1
            fused_scores[item_id] = fused_scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return fused_scores


def rank_of(item_id: int, ranked_ids: list[int]) -> int | None:
    """1-based position of an id in a list, or None if it is not there."""
    if item_id in ranked_ids:
        return ranked_ids.index(item_id) + 1
    return None


def retrieve_policy_chunks(
    database_session: Session,
    extracted_fields: dict,
    embedder: Embedder,
    search_mode: str = SEARCH_MODE_HYBRID,
    top_k: int = DEFAULT_TOP_K,
    treatment_type: str = "lumbar_spine_mri",
) -> list[RetrievedChunk]:
    """Return the top_k most relevant policy chunks for a case."""
    query_vector = embedder.embed_query(build_case_summary(extracted_fields))
    vector_ids = vector_search(
        database_session, query_vector, treatment_type, CANDIDATES_PER_SEARCH
    )

    keyword_ids: list[int] = []
    if search_mode == SEARCH_MODE_HYBRID:
        tsquery_text = build_tsquery(build_keyword_terms(extracted_fields))
        keyword_ids = keyword_search(
            database_session, tsquery_text, treatment_type, CANDIDATES_PER_SEARCH
        )

    fused_scores = reciprocal_rank_fusion([vector_ids, keyword_ids])
    best_ids = sorted(fused_scores, key=lambda chunk_id: fused_scores[chunk_id], reverse=True)
    best_ids = best_ids[:top_k]

    chunks_by_id = {}
    for chunk in database_session.scalars(select(PolicyChunk).where(PolicyChunk.id.in_(best_ids))):
        chunks_by_id[chunk.id] = chunk

    retrieved_chunks = []
    for chunk_id in best_ids:
        chunk = chunks_by_id[chunk_id]
        retrieved_chunks.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                policy_name=chunk.policy_name,
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                text=chunk.text,
                fused_score=round(fused_scores[chunk_id], 6),
                vector_rank=rank_of(chunk_id, vector_ids),
                keyword_rank=rank_of(chunk_id, keyword_ids),
            )
        )
    return retrieved_chunks
