import pytest
import numpy as np
from unittest.mock import patch
from backend.app.services.chunking_service import TextChunk
from backend.app.services.vector_index import VectorIndex
from backend.app.services.bm25_index import BM25Index
from backend.app.services.hybrid_retriever import HybridRetriever

def deterministic_embed_texts(self, texts, batch_size=32):
    dim = 384
    arr = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        for word in text.lower().split():
            idx = abs(hash(word)) % dim
            arr[i, idx] += 1.0
        norm = np.linalg.norm(arr[i])
        if norm > 0:
            arr[i] /= norm
        else:
            arr[i, 0] = 1.0
    return arr

def deterministic_embed_query(self, query):
    dim = 384
    arr = np.zeros((1, dim), dtype=np.float32)
    for word in query.lower().split():
        idx = abs(hash(word)) % dim
        arr[0, idx] += 1.0
    norm = np.linalg.norm(arr[0])
    if norm > 0:
        arr[0] /= norm
    else:
        arr[0, 0] = 1.0
    return arr

@pytest.fixture
def clean_indices(tmp_path):
    index_dir = str(tmp_path / "test_indices")
    with patch("backend.app.services.embedding_service.EmbeddingService.embed_texts", new=deterministic_embed_texts), \
         patch("backend.app.services.embedding_service.EmbeddingService.embed_query", new=deterministic_embed_query), \
         patch("backend.app.services.embedding_service.EmbeddingService.get_dimension", return_value=384):

        vector_idx = VectorIndex(index_dir=index_dir)
        bm25_idx = BM25Index(index_dir=index_dir)
        retriever = HybridRetriever(vector_index=vector_idx, bm25_index=bm25_idx)

        yield retriever, vector_idx, bm25_idx
        vector_idx.clear()
        bm25_idx.clear()

def test_sparse_bm25_retrieval(clean_indices):
    retriever, vector_idx, bm25_idx = clean_indices

    chunks = [
        TextChunk(
            chunk_id="doc1_p1_c0",
            document_id="doc1",
            page_number=1,
            chunk_index=0,
            content="The researchers evaluated the Transformer model on the WMT 2014 English-to-German dataset.",
            token_count=13,
            start_char=0,
            end_char=90
        ),
        TextChunk(
            chunk_id="doc1_p2_c1",
            document_id="doc1",
            page_number=2,
            chunk_index=1,
            content="Convolutional neural networks were applied for visual object detection and image classification.",
            token_count=12,
            start_char=0,
            end_char=96
        )
    ]
    bm25_idx.add_chunks(chunks)

    results = retriever.retrieve("Transformer English-to-German dataset", method="bm25", top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "doc1_p1_c0"
    assert results[0]["page_number"] == 1
    assert "Transformer" in results[0]["content"]

def test_dense_faiss_retrieval(clean_indices):
    retriever, vector_idx, bm25_idx = clean_indices

    chunks = [
        TextChunk(
            chunk_id="docA_p1_c0",
            document_id="docA",
            page_number=1,
            chunk_index=0,
            content="Deep reinforcement learning agents achieved human-level performance on Atari 2600 games.",
            token_count=12,
            start_char=0,
            end_char=89
        ),
        TextChunk(
            chunk_id="docA_p2_c1",
            document_id="docA",
            page_number=2,
            chunk_index=1,
            content="Support vector machines optimize the separating margin between two distinct classes of data points.",
            token_count=14,
            start_char=0,
            end_char=100
        )
    ]
    vector_idx.add_chunks(chunks)

    results = retriever.retrieve("reinforcement learning Atari games", method="dense", top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "docA_p1_c0"
    assert results[0]["page_number"] == 1

def test_hybrid_rrf_retrieval(clean_indices):
    retriever, vector_idx, bm25_idx = clean_indices

    chunks = [
        TextChunk(
            chunk_id="docH_p1_c0",
            document_id="docH",
            page_number=1,
            chunk_index=0,
            content="The experimental setup used an Adam optimizer with learning rate 0.001 and batch size 64.",
            token_count=15,
            start_char=0,
            end_char=90
        ),
        TextChunk(
            chunk_id="docH_p1_c1",
            document_id="docH",
            page_number=1,
            chunk_index=1,
            content="The evaluation showed a Top-1 accuracy of 88.5% on ImageNet validation benchmark.",
            token_count=12,
            start_char=91,
            end_char=175
        )
    ]
    vector_idx.add_chunks(chunks)
    bm25_idx.add_chunks(chunks)

    results = retriever.retrieve("learning rate Adam optimizer", method="hybrid", top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "docH_p1_c0"
    assert results[0]["retrieval_method"] == "hybrid"
    assert "rrf_score" in results[0]

def test_document_deletion_synchronization(clean_indices):
    retriever, vector_idx, bm25_idx = clean_indices

    c1 = TextChunk("doc1_c0", "doc1", 1, 0, "Document 1 passage regarding quantum computing.", 6, 0, 50)
    c2 = TextChunk("doc2_c0", "doc2", 1, 0, "Document 2 passage regarding classical computing.", 6, 0, 50)

    vector_idx.add_chunks([c1, c2])
    bm25_idx.add_chunks([c1, c2])

    # Delete doc1
    vector_idx.delete_document("doc1")
    bm25_idx.delete_document("doc1")

    dense_res = vector_idx.search("quantum", top_k=5)
    for r in dense_res:
        assert r["document_id"] != "doc1"

    bm25_res = bm25_idx.search("quantum", top_k=5)
    for r in bm25_res:
        assert r["document_id"] != "doc1"
