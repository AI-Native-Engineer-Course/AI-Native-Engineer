# How Ollama Relates to Docker

Ollama borrows much of its feel from Docker, which is why engineers who
already know containers tend to pick it up quickly. The two tools are not the
same thing, but the resemblance is deliberate.

## A familiar command surface

Ollama's command-line interface mirrors Docker's verbs. You `pull` a model
the way you pull an image, `run` it the way you run a container, `list` what
you have downloaded, and `rm` what you no longer need. This shared vocabulary
makes the learning curve gentle for anyone with Docker experience.

## Modelfile versus Dockerfile

Ollama packages a model using a **Modelfile**, which is conceptually similar
to a Dockerfile. A Modelfile starts `FROM` a base model, can layer on a
custom system prompt, set parameters such as temperature, and define a prompt
template. Building from a Modelfile produces a reusable, shareable model
package, just as a Dockerfile produces a reusable image.

## Where the analogy ends

Despite the similarities, Ollama is not running containers. It does not use
Linux namespaces or cgroups, and it is not a replacement for Docker. Under
the hood Ollama serves models through an inference engine (built on
llama.cpp) and exposes them over a local HTTP API. Docker isolates and ships
arbitrary software; Ollama specializes in packaging, serving, and running
language models. In short, Ollama feels Docker-like on the surface but solves
a narrower, model-specific problem.
