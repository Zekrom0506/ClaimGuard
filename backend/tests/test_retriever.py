"""Tests for keyword, vector and hybrid policy search."""

import json

import pytest

from app.core.database import SessionLocal
from app.services.embeddings import BGE_QUERY_PREFIX, SentenceTransformerEmbedder
from app.services.policy_chunker import section_number
from app.services.retriever import (
    SEARCH_MODE_VECTOR,
    build_case_summary,
    build_keyword_terms,
    build_tsquery,
    keyword_search,
    reciprocal_rank_fusion,
    retrieve_policy_chunks,
)
from tests.fakes import FakeEmbedder, load_recorded_response


def fields_from(file_name: str) -> dict:
    return json.loads(load_recorded_response(file_name))


def test_rrf_rewards_items_found_by_both_searches() -> None:
    fused = reciprocal_rank_fusion([[1, 2, 3], [3, 4]])
    # 3 is third in one list and first in the other; that beats 1 (first in only one list).
    assert fused[3] > fused[1]
    assert fused[1] > fused[4]


def test_rrf_uses_one_over_k_plus_rank() -> None:
    fused = reciprocal_rank_fusion([[7]], k=60)
    assert fused[7] == pytest.approx(1 / 61)


def test_rrf_with_one_empty_list_keeps_order_of_other() -> None:
    fused = reciprocal_rank_fusion([[5, 6], []])
    assert fused[5] > fused[6]


def test_tsquery_joins_terms_with_or_and_drops_unsafe_characters() -> None:
    assert build_tsquery(["M54.16", "red flag", "x'); DROP"]) == "M54.16 | red | flag | x | DROP"


def test_case_summary_mentions_missing_facts() -> None:
    extracted_fields = fields_from("extraction_eval_001.json")
    extracted_fields["physical_therapy_weeks"]["value"] = None
    summary = build_case_summary(extracted_fields)
    assert "conservative therapy is not documented" in summary


def test_keyword_terms_include_codes() -> None:
    keyword_terms = build_keyword_terms(fields_from("extraction_eval_001.json"))
    assert "72158" in keyword_terms
    assert "M54.16" in keyword_terms


def test_keyword_search_finds_exact_cpt_code(sample_policy_loaded: int) -> None:
    with SessionLocal() as database_session:
        chunk_ids = keyword_search(database_session, "72149", "lumbar_spine_mri", 5)
        found_chunks = retrieve_by_ids(database_session, chunk_ids)
    assert found_chunks
    assert all("72149" in chunk_text for chunk_text in found_chunks)


def retrieve_by_ids(database_session, chunk_ids: list[int]) -> list[str]:
    from app.models.policy_chunk import PolicyChunk

    texts = []
    for chunk_id in chunk_ids:
        texts.append(database_session.get(PolicyChunk, chunk_id).text)
    return texts


def test_hybrid_search_returns_five_chunks_with_sources(sample_policy_loaded: int) -> None:
    with SessionLocal() as database_session:
        retrieved = retrieve_policy_chunks(
            database_session, fields_from("extraction_eval_001.json"), FakeEmbedder()
        )
    assert len(retrieved) == 5
    for chunk in retrieved:
        assert chunk.policy_name == "Sample Lumbar Mri Policy"
        assert chunk.page_number >= 1
        assert chunk.section_title


def test_hybrid_search_finds_conservative_therapy_section(sample_policy_loaded: int) -> None:
    with SessionLocal() as database_session:
        retrieved = retrieve_policy_chunks(
            database_session, fields_from("extraction_eval_033.json"), FakeEmbedder()
        )
    found_sections = [section_number(chunk.section_title) for chunk in retrieved]
    assert "2.2" in found_sections


def test_vector_only_mode_has_no_keyword_ranks(sample_policy_loaded: int) -> None:
    with SessionLocal() as database_session:
        retrieved = retrieve_policy_chunks(
            database_session,
            fields_from("extraction_eval_001.json"),
            FakeEmbedder(),
            search_mode=SEARCH_MODE_VECTOR,
        )
    assert all(chunk.keyword_rank is None for chunk in retrieved)


def test_other_treatment_types_are_not_searched(sample_policy_loaded: int) -> None:
    with SessionLocal() as database_session:
        retrieved = retrieve_policy_chunks(
            database_session,
            fields_from("extraction_eval_001.json"),
            FakeEmbedder(),
            treatment_type="knee_mri",
        )
    assert retrieved == []


def test_real_embedder_adds_query_prefix(monkeypatch) -> None:
    received_texts = []

    class RecordingModel:
        def encode(self, text, normalize_embeddings):
            received_texts.append(text)
            import numpy

            return numpy.zeros(3)

    embedder = SentenceTransformerEmbedder("unused")
    monkeypatch.setattr(embedder, "_get_model", lambda: RecordingModel())
    embedder.embed_query("back pain")
    assert received_texts == [BGE_QUERY_PREFIX + "back pain"]
