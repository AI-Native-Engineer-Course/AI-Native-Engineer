# Embeddings and Vector Search

An embedding is a list of numbers that represents the meaning of a piece of
text as a point in a high-dimensional space. Texts with similar meaning land
close together, which is what makes semantic search possible.

## Dense (semantic) retrieval

In a RAG pipeline, every chunk is embedded once and stored in a vector
database such as Chroma. At query time the question is embedded with the same
model, and the database returns the chunks whose vectors are nearest to the
query vector, usually by cosine similarity. This is called dense retrieval
because it relies on dense numeric vectors rather than exact keywords.

## Using a dedicated embedding model

It is best to embed with a model built for the job, such as
`nomic-embed-text`, rather than reusing a chat model. Dedicated embedding
models produce more useful vectors and are far cheaper to run. The one rule
that must hold is that the documents and the queries are embedded with the
*same* model, so they share a vector space.

## Strengths and limits

Dense retrieval shines when the query and the answer use different words for
the same idea, because it matches on meaning. Its weakness is rare exact
terms, codes, or names, where a keyword method can do better. That weakness is
exactly why production systems combine dense retrieval with a lexical method.
