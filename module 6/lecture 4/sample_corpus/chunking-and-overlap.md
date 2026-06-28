# Chunking and Overlap

Before documents can be retrieved in a RAG system they are split into smaller
pieces called chunks. Chunking matters because embedding models and context
windows both work best with focused, bounded passages rather than whole
documents.

## Why we use chunk overlap

When you split a document at a fixed size, an idea or sentence can land right
on a chunk boundary and get cut in half. Overlap solves this by repeating a
small amount of text from the end of one chunk at the start of the next. That
shared region preserves the surrounding context across the boundary, so a
sentence split between two chunks still appears intact in at least one of
them.

Without overlap, a query that matches text straddling a boundary may retrieve
a chunk that is missing the other half of the answer. With overlap, the
context that spans the boundary is captured, which improves retrieval recall
and keeps answers coherent.

## Choosing chunk size and overlap

Chunk size trades specificity against context: smaller chunks are more
precise but may lose surrounding meaning, while larger chunks carry more
context but dilute relevance. A common starting point is a few hundred
characters or tokens per chunk with an overlap of around ten to fifteen
percent of the chunk size. The overlap should be large enough to span a
typical sentence so that no single boundary can destroy meaning.
