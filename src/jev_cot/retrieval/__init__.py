"""
jev_cot.retrieval
==================
Pluggable retrieval layer for the JEV-CoT pipeline (Phase 4, FR-11).

Submodules
----------
base              RetrievalBackend ABC, typed Chunk/RetrievedChunk/RetrievalQuery/
                   RetrievalResult models, and the document-id/tagging contract
                   every backend shares.
faiss_retriever    FaissRetriever — the FAISS + sentence-transformers backend.
ingest             Chunk, embed, and index a local document corpus into the
                   on-disk FAISS artifacts a FaissRetriever loads.

Usage::

    from jev_cot.retrieval.faiss_retriever import FaissRetriever

    retriever = FaissRetriever.from_index_dir("data/processed/faiss_index")
    result = retriever.retrieve(company="MSFT", period="FY2023", query="revenue")
"""

from __future__ import annotations
