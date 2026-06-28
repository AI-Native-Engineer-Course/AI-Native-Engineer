# Retrieval-Augmented Generation Overview

Retrieval-Augmented Generation (RAG) is a pattern for grounding a language
model's answers in your own documents. Instead of relying only on what the
model learned during training, RAG retrieves relevant passages at query time
and places them in the prompt, so the model answers from supplied evidence.

## The pipeline

A typical RAG pipeline has a few stages. Documents are loaded and split into
chunks; each chunk is indexed for retrieval; at query time the most relevant
chunks are retrieved, optionally reranked, and assembled into a prompt; and
the model generates an answer that cites the sources it used. This course
builds exactly that pipeline, starting from a minimal version and upgrading it
into a production-shaped one.

## Why grounding matters

Grounding the answer in retrieved sources reduces hallucination and lets the
system cite where each claim came from. A well-designed RAG prompt also tells
the model to answer only from the provided sources and to say it does not know
when the sources do not contain the answer, rather than guessing.

## The AI-Native Engineer course

This page is part of a small synthetic corpus used in the local LLMs and RAG
module of the AI-Native Engineer course. The corpus is intentionally tiny so
the hands-on demo runs in under a minute on a laptop while still exercising
loading, chunking, hybrid retrieval, reranking, and grounded generation.
