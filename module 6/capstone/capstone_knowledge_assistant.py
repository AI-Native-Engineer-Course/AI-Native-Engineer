"""
capstone_knowledge_assistant.py

Module 6 Capstone — "Your Private Knowledge Assistant"

A complete, runnable, 100% local privacy-preserving knowledge assistant.
Ties together every concept from Module 6:

  Lecture 6.1 — tokens, parameters, sampling (used for transparency mode)
  Lecture 6.2 — Ollama local inference (no cloud, no API key)
  Lecture 6.3 — Modelfile persona, embeddings (nomic-embed-text)
  Lecture 6.4 — chunking, hybrid retrieval, rerank, citation-aware
                generation, eval harness

Usage:
    python capstone_knowledge_assistant.py ingest <corpus_dir>
    python capstone_knowledge_assistant.py ask "<question>"
    python capstone_knowledge_assistant.py chat
    python capstone_knowledge_assistant.py eval

Prereqs:
    pip install ollama chromadb langchain-text-splitters rank_bm25
    ollama pull llama3.2
    ollama pull nomic-embed-text
    ollama create kb-assistant -f ./Modelfile.capstone
"""

import sys
import os
import json
import re
import glob
import time
from pathlib import Path

import ollama
import chromadb
from rank_bm25 import BM25Okapi
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------- Configuration ----------

GEN_MODEL = "kb-assistant"                  # the persona model built from Modelfile
EMBED_MODEL = "nomic-embed-text"
RERANK_MODEL = "llama3.2"                   # use the base model for reranking
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
DENSE_TOP_K = 8
SPARSE_TOP_K = 8
HYBRID_TOP_K = 8
RERANK_TOP_K = 4
RRF_K = 60
CHROMA_DIR = ".kb_chroma"
COLLECTION = "kb-corpus"
BM25_CACHE = ".kb_bm25.json"


# ---------- Helpers ----------

def _client():
    """Return a persistent Chroma client + the collection (created if absent)."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    coll = client.get_or_create_collection(name=COLLECTION)
    return client, coll


def _tokenize(text):
    """Cheap tokenizer for BM25 — lowercase alphanumeric word split."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _embed(text):
    """One embedding call to Ollama."""
    resp = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return resp["embedding"]


# ---------- Ingestion ----------

def ingest(corpus_dir):
    """Chunk + index every .md / .txt file in corpus_dir."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        print(f"ERROR: {corpus_dir} does not exist.")
        sys.exit(1)

    files = sorted(
        glob.glob(str(corpus_dir / "*.md")) + glob.glob(str(corpus_dir / "*.txt"))
    )
    if not files:
        print(f"ERROR: no .md or .txt files found in {corpus_dir}")
        sys.exit(1)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    # Rebuild the collection from scratch each ingest so re-runs are clean.
    client, _ = _client()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    coll = client.get_or_create_collection(name=COLLECTION)

    all_ids, all_docs, all_metas = [], [], []
    for fp in files:
        fname = os.path.basename(fp)
        text = Path(fp).read_text(encoding="utf-8")
        chunks = splitter.split_text(text)
        print(f"  {fname}: {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            cid = f"{fname}::chunk{i}"
            all_ids.append(cid)
            all_docs.append(chunk)
            all_metas.append({"filename": fname, "chunk_id": f"chunk{i}"})

    print(f"\nEmbedding {len(all_docs)} chunks with {EMBED_MODEL} ...")
    t0 = time.time()
    embeddings = [_embed(doc) for doc in all_docs]
    coll.add(ids=all_ids, documents=all_docs, metadatas=all_metas,
             embeddings=embeddings)
    print(f"  done in {time.time() - t0:.1f}s")

    # Cache the raw chunks so BM25 can be rebuilt without re-reading files.
    Path(BM25_CACHE).write_text(json.dumps({
        "ids": all_ids, "docs": all_docs, "metas": all_metas,
    }), encoding="utf-8")
    print(f"\nIngest complete: {len(files)} files, {len(all_docs)} chunks indexed.")


# ---------- Retrieval (hybrid: dense + sparse + RRF) ----------

def _load_bm25():
    """Load the cached chunks and build the BM25 index in memory."""
    if not Path(BM25_CACHE).exists():
        print("ERROR: no index found — run `ingest <corpus_dir>` first.")
        sys.exit(1)
    cache = json.loads(Path(BM25_CACHE).read_text(encoding="utf-8"))
    bm25 = BM25Okapi([_tokenize(d) for d in cache["docs"]])
    return bm25, cache


def hybrid_retrieve(question):
    """Dense (Chroma) + sparse (BM25) retrieval fused with Reciprocal Rank Fusion."""
    _, coll = _client()
    bm25, cache = _load_bm25()

    # Dense leg
    q_emb = _embed(question)
    dense = coll.query(query_embeddings=[q_emb], n_results=DENSE_TOP_K)
    dense_ids = dense["ids"][0]

    # Sparse leg
    scores = bm25.get_scores(_tokenize(question))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    sparse_ids = [cache["ids"][i] for i in ranked[:SPARSE_TOP_K]]

    # Reciprocal Rank Fusion
    rrf = {}
    for rank, cid in enumerate(dense_ids):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
    for rank, cid in enumerate(sparse_ids):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)

    fused = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)[:HYBRID_TOP_K]
    id_to_idx = {cid: i for i, cid in enumerate(cache["ids"])}
    results = []
    for cid, score in fused:
        idx = id_to_idx[cid]
        results.append({
            "id": cid,
            "text": cache["docs"][idx],
            "meta": cache["metas"][idx],
            "rrf": score,
        })
    return results


# ---------- Reranking (LLM-as-reranker) ----------

def rerank(question, candidates):
    """Score each candidate 0-10 for relevance with the base model; keep the top N."""
    scored = []
    for cand in candidates:
        prompt = (
            "Rate how useful this passage is for answering the question.\n"
            "Respond with ONLY an integer 0-10. No other text.\n\n"
            f"QUESTION: {question}\n\nPASSAGE:\n{cand['text']}\n\nSCORE:"
        )
        resp = ollama.generate(model=RERANK_MODEL, prompt=prompt,
                               options={"temperature": 0.0})
        m = re.search(r"\d+", resp["response"])
        score = int(m.group()) if m else 0
        scored.append((min(score, 10), cand))
    scored.sort(key=lambda sc: sc[0], reverse=True)
    return [cand for _, cand in scored[:RERANK_TOP_K]]


# ---------- Generation (citation-required) ----------

def _build_context(chunks):
    blocks = []
    for c in chunks:
        tag = f"[SOURCE: {c['meta']['filename']}, {c['meta']['chunk_id']}]"
        blocks.append(f"{tag}\n{c['text']}")
    return "\n\n---\n\n".join(blocks)


def answer(question, verbose=True):
    """Full pipeline: hybrid retrieve -> rerank -> cited generation."""
    if verbose:
        print("  [1/3] hybrid retrieval (dense + BM25 + RRF) ...")
    candidates = hybrid_retrieve(question)
    if verbose:
        print(f"  [2/3] reranking {len(candidates)} candidates with {RERANK_MODEL} ...")
    top = rerank(question, candidates)
    if verbose:
        print(f"  [3/3] generating with {GEN_MODEL} ...\n")

    context = _build_context(top)
    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    resp = ollama.generate(model=GEN_MODEL, prompt=prompt)
    return resp["response"].strip()


# ---------- Chat (multi-turn REPL) ----------

def chat():
    """Interactive loop. Each turn runs the full RAG pipeline."""
    print("kb-assistant chat — type 'exit' to quit.\n")
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit"):
            break
        print()
        print("kb> " + answer(q, verbose=False))
        print()


# ---------- Eval harness ----------

EVAL_QUESTIONS = [
    {
        "question": "What is the default chunk size recommended for ingestion?",
        "must_cite": "chunking_guide.md",
    },
    {
        "question": "Which retrieval strategy combines dense and sparse search?",
        "must_cite": "retrieval_strategies.md",
    },
    {
        "question": "What temperature should the assistant persona use and why?",
        "must_cite": "model_configuration.md",
    },
    {
        "question": "What must the assistant do when the context does not answer "
                    "the question?",
        "must_cite": "assistant_policy.md",
    },
]

JUDGE_PROMPT = """You are an evaluation judge. Score the ANSWER to the QUESTION.

Return ONLY a JSON object, no markdown, with keys:
  "relevance": integer 0-10 (does the answer address the question?)
  "grounding": integer 0-10 (is every claim supported with a [SOURCE: ...] citation?)
  "rationale": one sentence.

QUESTION: {question}

ANSWER:
{answer}
"""


def eval_suite():
    """Run every eval question through the pipeline and judge the results."""
    print("Running eval suite ...\n")
    pass_count = 0
    relevance_scores, grounding_scores = [], []

    for item in EVAL_QUESTIONS:
        print(f"  Q: {item['question']}")
        t0 = time.time()
        ans = answer(item["question"], verbose=False)
        dt = time.time() - t0

        judge = ollama.generate(
            model=RERANK_MODEL,
            prompt=JUDGE_PROMPT.format(question=item["question"], answer=ans),
            options={"temperature": 0.0},
        )
        raw = judge["response"]
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            scores = json.loads(m.group())
        except Exception:
            scores = {"relevance": 0, "grounding": 0, "rationale": "parse error"}

        cited = item["must_cite"] in ans
        passed = scores["relevance"] >= 7 and scores["grounding"] >= 7 and cited
        pass_count += int(passed)
        relevance_scores.append(scores["relevance"])
        grounding_scores.append(scores["grounding"])

        print(f"    relevance={scores['relevance']} grounding={scores['grounding']} "
              f"cited_expected={cited} time={dt:.1f}s -> {'PASS' if passed else 'FAIL'}")
        print(f"    rationale: {scores.get('rationale','')}\n")

    n = len(EVAL_QUESTIONS)
    print("=" * 60)
    print(f"  avg relevance : {sum(relevance_scores)/n:.1f}")
    print(f"  avg grounding : {sum(grounding_scores)/n:.1f}")
    print(f"  passed        : {pass_count}/{n}")
    print(f"  RESULT        : {'PASS' if pass_count == n else 'FAIL'}")
    print("=" * 60)


# ---------- CLI ----------

def usage():
    print(__doc__)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]
    if cmd == "ingest":
        if len(sys.argv) < 3:
            print("usage: capstone_knowledge_assistant.py ingest <corpus_dir>")
            sys.exit(1)
        ingest(sys.argv[2])
    elif cmd == "ask":
        if len(sys.argv) < 3:
            print('usage: capstone_knowledge_assistant.py ask "<question>"')
            sys.exit(1)
        print(answer(sys.argv[2]))
    elif cmd == "chat":
        chat()
    elif cmd == "eval":
        eval_suite()
    else:
        usage()


if __name__ == "__main__":
    main()
