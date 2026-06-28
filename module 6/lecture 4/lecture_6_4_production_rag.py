"""
lecture_6_4_production_rag.py
-----------------------------
Companion script for Module 6, Lecture 6.4 hands-on exercise.

A production-shaped local RAG pipeline. This is the upgrade from the mini-RAG
in Lecture 6.3. New pieces:
  - Real document loading from a folder of markdown files
  - Recursive character chunking with overlap
  - Hybrid retrieval (semantic + BM25, fused with Reciprocal Rank Fusion)
  - Reranking pass over the fused candidates using an LLM-as-reranker prompt
  - Citation-aware prompt assembly
  - A small built-in evaluation harness

Prerequisites:
  - Ollama installed and running
  - Models pulled:
      ollama pull llama3.2
      ollama pull nomic-embed-text
  - Python 3.10+
  - pip install ollama chromadb langchain-text-splitters rank-bm25

A small corpus is shipped alongside this script in ./sample_corpus/. Each file
in that folder is a synthetic "wiki page" about an aspect of the AI-Native
Engineer course. The corpus is intentionally small so the whole demo runs in
under a minute on a laptop.
"""

from __future__ import annotations

import os
import re
import math
from pathlib import Path
from typing import Iterable

import ollama
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

CHAT_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"
CORPUS_DIR = Path(__file__).parent / "sample_corpus"

CHUNK_SIZE = 400        # characters, not tokens — fast and good enough
CHUNK_OVERLAP = 50
TOP_K_DENSE = 8         # vector retriever
TOP_K_SPARSE = 8        # BM25 retriever
TOP_K_FINAL = 4         # how many chunks we send to the LLM after reranking


# ---------------------------------------------------------------------------
# 1. Load and chunk
# ---------------------------------------------------------------------------

def load_documents(folder: Path) -> list[dict]:
    """Read every .md file in the folder into a list of {id, source, text}."""
    docs = []
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        docs.append({"id": path.stem, "source": path.name, "text": text})
    if not docs:
        raise FileNotFoundError(
            f"No .md files found under {folder}. "
            "Make sure sample_corpus/ exists next to this script."
        )
    print(f"Loaded {len(docs)} documents from {folder}")
    return docs


def chunk_documents(docs: list[dict]) -> list[dict]:
    """Recursive character splitting with overlap. One chunk per dict."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for doc in docs:
        pieces = splitter.split_text(doc["text"])
        for i, piece in enumerate(pieces):
            chunks.append(
                {
                    "id": f"{doc['id']}::chunk-{i:03d}",
                    "source": doc["source"],
                    "text": piece,
                }
            )
    print(f"Split into {len(chunks)} chunks "
          f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


# ---------------------------------------------------------------------------
# 2. Build the dense (vector) and sparse (BM25) indexes
# ---------------------------------------------------------------------------

def build_dense_index(chunks: list[dict]):
    """Embed every chunk with Ollama and stuff into an in-memory Chroma collection."""
    client = chromadb.Client()
    try:
        client.delete_collection("prod_rag")
    except Exception:
        pass
    collection = client.create_collection(name="prod_rag")

    print(f"Embedding {len(chunks)} chunks with {EMBED_MODEL}...")
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [{"source": c["source"]} for c in chunks]
    vectors = [
        ollama.embeddings(model=EMBED_MODEL, prompt=t)["embedding"]
        for t in texts
    ]
    collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
    print(f"Dense index ready: {collection.count()} vectors\n")
    return collection


def build_sparse_index(chunks: list[dict]):
    """Tokenize chunk text and build a BM25 index alongside the dense one."""
    tokenized = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    return bm25, chunks  # we keep the chunk list to map indices back


def _tokenize(text: str) -> list[str]:
    """Crude word-level tokenizer for BM25. Lowercase + strip punctuation."""
    return re.findall(r"[a-z0-9]+", text.lower())


# ---------------------------------------------------------------------------
# 3. Retrieve from both, fuse with Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def dense_retrieve(collection, query: str, k: int):
    qvec = ollama.embeddings(model=EMBED_MODEL, prompt=query)["embedding"]
    res = collection.query(query_embeddings=[qvec], n_results=k)
    return res["ids"][0]   # ordered best to worst


def sparse_retrieve(bm25: BM25Okapi, chunks: list[dict], query: str, k: int):
    scores = bm25.get_scores(_tokenize(query))
    # argsort descending, take top k
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [chunks[i]["id"] for i in ranked]


def reciprocal_rank_fusion(*ranked_lists: list[str], k: int = 60) -> list[str]:
    """Classic RRF. Higher rank => higher score. Lower position in list = better."""
    scores: dict[str, float] = {}
    for ranking in ranked_lists:
        for position, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position + 1)
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [doc_id for doc_id, _score in fused]


# ---------------------------------------------------------------------------
# 4. Rerank with an LLM-as-judge prompt
# ---------------------------------------------------------------------------

def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """
    Score each candidate's relevance to the query on a 0-10 scale using the
    chat model itself as a cross-encoder. Slower than a real cross-encoder
    like bge-reranker, but it works fully offline with a single model.
    """
    rescored = []
    for c in candidates:
        prompt = (
            "You are a relevance judge. On a scale of 0 to 10, rate how well "
            "the candidate passage answers the question. Respond with a single "
            "integer and nothing else.\n\n"
            f"Question: {query}\n\n"
            f"Candidate passage:\n{c['text']}\n\n"
            "Score (0-10):"
        )
        resp = ollama.generate(
            model=CHAT_MODEL,
            prompt=prompt,
            options={"temperature": 0.0, "num_predict": 4},
        )
        raw = resp["response"].strip()
        match = re.search(r"\d+", raw)
        score = int(match.group(0)) if match else 0
        score = min(max(score, 0), 10)
        rescored.append((score, c))

    rescored.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _score, c in rescored[:top_k]]


# ---------------------------------------------------------------------------
# 5. Assemble prompt and generate
# ---------------------------------------------------------------------------

def assemble_prompt(query: str, chunks: list[dict]) -> str:
    """
    Put best chunks at the ends of the context block — the "lost in the
    middle" effect means start and end positions get the most attention.
    """
    if len(chunks) > 2:
        ordered = [chunks[0]] + chunks[2:] + [chunks[1]]
    else:
        ordered = chunks

    blocks = []
    for i, c in enumerate(ordered, start=1):
        blocks.append(
            f"[Source {i} — {c['source']}]\n{c['text']}"
        )
    context = "\n\n".join(blocks)

    return (
        "Answer the question using ONLY the sources below. Cite the source "
        "number(s) you used in square brackets like [1] or [1, 3]. If the "
        "sources do not contain the answer, respond exactly with: "
        "\"I don't know from the provided context.\"\n\n"
        f"<sources>\n{context}\n</sources>\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )


def generate(query: str, top_chunks: list[dict]) -> str:
    prompt = assemble_prompt(query, top_chunks)
    response = ollama.generate(
        model=CHAT_MODEL,
        prompt=prompt,
        options={"temperature": 0.2, "num_ctx": 4096},
    )
    return response["response"].strip()


# ---------------------------------------------------------------------------
# 6. End-to-end query function
# ---------------------------------------------------------------------------

def answer_question(question, collection, bm25, chunks):
    chunk_lookup = {c["id"]: c for c in chunks}

    dense_ids = dense_retrieve(collection, question, TOP_K_DENSE)
    sparse_ids = sparse_retrieve(bm25, chunks, question, TOP_K_SPARSE)
    fused_ids = reciprocal_rank_fusion(dense_ids, sparse_ids)[:TOP_K_DENSE]
    fused_chunks = [chunk_lookup[i] for i in fused_ids]

    print(f"\n  Fused candidates: {len(fused_chunks)}; reranking...")
    top_chunks = rerank(question, fused_chunks, TOP_K_FINAL)

    print("  Final chunks used (by source):")
    for i, c in enumerate(top_chunks, start=1):
        print(f"    [{i}] {c['source']} :: {c['id']}")

    return generate(question, top_chunks)


# ---------------------------------------------------------------------------
# 7. Tiny evaluation harness
# ---------------------------------------------------------------------------

EVAL_SET = [
    {
        "question": "What is the role of a system prompt in a local LLM?",
        "must_mention_any": ["system prompt", "instruction", "behavior"],
    },
    {
        "question": "Which Ollama command downloads a new model?",
        "must_mention_any": ["pull", "ollama pull"],
    },
    {
        "question": "Why do we use chunk overlap when splitting documents?",
        "must_mention_any": ["context", "boundary", "overlap"],
    },
]


def evaluate(collection, bm25, chunks) -> None:
    print("\n" + "=" * 70)
    print("EVALUATION — three questions, simple keyword-presence check")
    print("=" * 70)
    passed = 0
    for case in EVAL_SET:
        q = case["question"]
        print(f"\nQ: {q}")
        answer = answer_question(q, collection, bm25, chunks)
        print(f"A: {answer}")
        lower = answer.lower()
        hit = any(term.lower() in lower for term in case["must_mention_any"])
        print(f"  Pass: {hit}  (expected any of: {case['must_mention_any']})")
        passed += int(hit)
    print(f"\nFinal: {passed}/{len(EVAL_SET)} passed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building pipeline...")
    docs = load_documents(CORPUS_DIR)
    chunks = chunk_documents(docs)
    collection = build_dense_index(chunks)
    bm25, _ = build_sparse_index(chunks)

    print("\n" + "=" * 70)
    print("INTERACTIVE QUERY (one example, then evaluation runs)")
    print("=" * 70)
    sample_q = "How does Ollama relate to Docker?"
    print(f"\nQ: {sample_q}")
    answer = answer_question(sample_q, collection, bm25, chunks)
    print(f"A: {answer}")

    evaluate(collection, bm25, chunks)
