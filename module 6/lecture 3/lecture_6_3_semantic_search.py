"""
lecture_6_3_semantic_search.py
------------------------------
Companion script for Module 6, Lecture 6.3 hands-on exercise.

Demonstrates the end-to-end retrieve-then-generate loop in its simplest form:
  1. Embed a handful of short documents using a local Ollama embedding model.
  2. Store the embeddings in an in-memory ChromaDB collection.
  3. Embed a user query and retrieve the top-K most similar documents.
  4. Stuff the retrieved documents into a prompt and ask the LLM to answer.

This is "mini-RAG" — the absolute smallest end-to-end version of the
architecture we expand on in Lecture 6.4.

Prerequisites:
  - Ollama installed and running
  - Models pulled:
      ollama pull llama3.2
      ollama pull nomic-embed-text
  - Python 3.10+
  - pip install ollama chromadb
"""

from __future__ import annotations

import ollama
import chromadb

CHAT_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"


# ---------------------------------------------------------------------------
# A small in-memory "knowledge base"
# ---------------------------------------------------------------------------
# In real life these would be paragraphs from your documentation, your wiki,
# your transcripts. Here we use seven short snippets so you can read them
# all and check the retrieval results visually.

DOCUMENTS = [
    {
        "id": "doc-1",
        "text": (
            "Python list comprehensions create a new list by applying an "
            "expression to each item in an iterable, optionally filtering "
            "with an if clause. Example: [x*x for x in range(10) if x % 2]."
        ),
    },
    {
        "id": "doc-2",
        "text": (
            "PostgreSQL uses Multi-Version Concurrency Control (MVCC) so "
            "readers never block writers and writers never block readers. "
            "Each transaction sees a consistent snapshot of the database."
        ),
    },
    {
        "id": "doc-3",
        "text": (
            "Docker containers package an application with its dependencies "
            "into a single immutable image. Images are layered, cached, and "
            "shareable through registries like Docker Hub."
        ),
    },
    {
        "id": "doc-4",
        "text": (
            "Git rebase rewrites commit history by replaying commits onto a "
            "new base. Use it for tidying up local feature branches; never "
            "rebase a branch that has already been pushed and shared."
        ),
    },
    {
        "id": "doc-5",
        "text": (
            "The Python GIL (Global Interpreter Lock) prevents multiple "
            "native threads from executing Python bytecode simultaneously "
            "in CPython. Use multiprocessing or asyncio for true concurrency."
        ),
    },
    {
        "id": "doc-6",
        "text": (
            "Indexes in PostgreSQL speed up SELECT queries at the cost of "
            "slower INSERT and UPDATE operations. B-tree indexes are the "
            "default and work well for equality and range comparisons."
        ),
    },
    {
        "id": "doc-7",
        "text": (
            "Kubernetes orchestrates containerized applications across a "
            "cluster, handling scheduling, scaling, and self-healing. "
            "Pods are the smallest deployable unit."
        ),
    },
]


# ---------------------------------------------------------------------------
# Step 1 — Embed and index
# ---------------------------------------------------------------------------

def embed(text: str) -> list[float]:
    """Get an embedding vector for a single string using Ollama."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def build_index() -> chromadb.Collection:
    """Create an in-memory Chroma collection and add all documents."""
    client = chromadb.Client()
    # Drop the collection if it already exists (handy for re-runs)
    try:
        client.delete_collection("mini_rag")
    except Exception:
        pass
    collection = client.create_collection(name="mini_rag")

    print(f"Embedding {len(DOCUMENTS)} documents with {EMBED_MODEL}...")
    ids = [d["id"] for d in DOCUMENTS]
    texts = [d["text"] for d in DOCUMENTS]
    vectors = [embed(t) for t in texts]

    collection.add(ids=ids, embeddings=vectors, documents=texts)
    print(f"Index built: {collection.count()} documents stored.\n")
    return collection


# ---------------------------------------------------------------------------
# Step 2 — Retrieve
# ---------------------------------------------------------------------------

def retrieve(collection: chromadb.Collection, query: str, k: int = 3):
    """Return the top-k most semantically similar documents for the query."""
    query_vector = embed(query)
    results = collection.query(query_embeddings=[query_vector], n_results=k)
    # Pair ids, texts, and distances for inspection
    return list(
        zip(
            results["ids"][0],
            results["documents"][0],
            results["distances"][0],
        )
    )


# ---------------------------------------------------------------------------
# Step 3 — Generate with retrieved context
# ---------------------------------------------------------------------------

def generate_answer(query: str, retrieved: list[tuple]) -> str:
    """Build a RAG prompt and ask the LLM to answer from the context."""
    context_block = "\n\n".join(
        f"[Source {i + 1}, id={doc_id}]\n{text}"
        for i, (doc_id, text, _dist) in enumerate(retrieved)
    )

    prompt = f"""Answer the question using ONLY the context below.
If the context does not contain the answer, say "I don't know from the provided context."
Cite the source numbers you used in square brackets.

<context>
{context_block}
</context>

Question: {query}

Answer:"""

    response = ollama.generate(
        model=CHAT_MODEL,
        prompt=prompt,
        options={"temperature": 0.2, "num_ctx": 4096},
    )
    return response["response"].strip()


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

QUERIES = [
    # Direct keyword overlap with doc-2 and doc-6
    "How does PostgreSQL handle concurrent reads and writes?",
    # No keyword overlap with any doc, but doc-1 is the right answer
    "How do I build a list with squared values in one line?",
    # Conceptual overlap with doc-5
    "Why can't I get speedups from threading in Python?",
    # Should retrieve nothing relevant and respond with "I don't know"
    "What is the boiling point of mercury?",
]


def main() -> None:
    collection = build_index()

    for q in QUERIES:
        print("=" * 70)
        print(f"QUERY: {q}")
        print("=" * 70)
        retrieved = retrieve(collection, q, k=3)
        for i, (doc_id, text, dist) in enumerate(retrieved, start=1):
            print(f"\n  Top {i}: {doc_id} (distance={dist:.3f})")
            print(f"    {text[:90]}...")

        answer = generate_answer(q, retrieved)
        print(f"\nANSWER:\n  {answer}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[Error] {type(e).__name__}: {e}")
        print("Have you pulled both models?")
        print("  ollama pull llama3.2")
        print("  ollama pull nomic-embed-text")
