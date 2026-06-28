# BM25 and Hybrid Search

BM25 is a classic keyword ranking algorithm. It scores how well a document
matches a query based on term frequency, how rare each term is across the
whole corpus, and the length of the document. Because it matches exact tokens,
BM25 is excellent at finding rare names, error codes, and specific jargon that
a semantic model might gloss over.

## Sparse retrieval

BM25 is called sparse retrieval because it works over sparse keyword vectors
rather than dense embeddings. It needs no model and no GPU, runs instantly,
and is fully deterministic, which makes it a cheap and reliable complement to
semantic search.

## Why hybrid search

Dense and sparse retrieval fail in different ways: dense search can miss exact
terms, and sparse search can miss paraphrases. Hybrid search runs both and
combines their results, so a chunk that either method ranks highly still has a
chance to surface. In practice this raises recall noticeably over either
method alone.

## Reciprocal Rank Fusion

The challenge in combining two retrievers is that cosine similarity scores and
BM25 scores live on completely different scales and cannot be added directly.
Reciprocal Rank Fusion (RRF) sidesteps this by ignoring the raw scores and
using only rank position. Each result contributes a score of one divided by a
constant plus its position, and the contributions are summed across both
lists. Chunks ranked highly by both retrievers rise to the top, with no score
normalization required.
