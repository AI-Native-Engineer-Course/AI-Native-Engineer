# Reranking Retrieved Results

Retrieval is tuned for recall: it casts a wide net and returns more candidates
than you actually want to show the model. Reranking is the second stage that
reorders those candidates by relevance and keeps only the strongest few. The
pattern is to retrieve wide, then rerank narrow.

## Cross-encoders

The most accurate rerankers are cross-encoders. Unlike an embedding model,
which encodes the query and a passage separately, a cross-encoder reads the
query and the passage together and outputs a single relevance score. Seeing
both at once lets it judge relevance far more precisely, at the cost of being
slower, since it must run once per candidate. Models such as `bge-reranker`
are purpose-built for this.

## LLM as a reranker

When you do not have a dedicated cross-encoder, you can prompt a chat model to
act as a relevance judge: give it the question and one candidate passage and
ask for a score from zero to ten. This works fully offline with a single
model, but it is slow because it needs one model call per candidate, and the
scores can be noisier than a trained reranker. Setting the temperature to zero
keeps the scores stable.

## Why it helps

Reranking matters because the order and quality of the chunks placed in the
prompt strongly affect the final answer. Sending four well-chosen chunks beats
sending eight mediocre ones, both for answer quality and for keeping the
context window small.
