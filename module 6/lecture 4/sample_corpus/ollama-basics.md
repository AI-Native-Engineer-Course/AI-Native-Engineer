# Ollama Basics

Ollama is a tool for running large language models locally on your own
machine. It wraps the model weights, a runtime, and a simple HTTP server
behind a single command-line interface, so you can experiment with models
without sending any data to a cloud provider.

## Pulling models

To download a new model you use the `pull` command. The general form is:

    ollama pull <model-name>

For example, `ollama pull llama3.2` downloads the Llama 3.2 chat model, and
`ollama pull nomic-embed-text` downloads a dedicated embedding model. The
first pull fetches the weights over the network; after that the model is
cached locally and starts almost instantly.

## Running and listing models

Once a model is pulled, `ollama run llama3.2` starts an interactive chat
session, and `ollama list` shows every model you have downloaded. The
background server exposes an HTTP API on port 11434, which is what Python
clients such as the `ollama` package talk to under the hood.

## Why local models

Running models locally keeps your prompts and documents private, removes
per-token API costs, and lets the whole pipeline work offline. The trade-off
is that you are limited by your own hardware, so smaller quantized models are
common on laptops.
