# System Prompts in Local LLMs

A system prompt is a special instruction given to a language model before any
user messages. Its role is to set the model's behavior, persona, and ground
rules for the conversation that follows. Where a user message asks for
something specific, the system prompt shapes *how* the model responds to
everything.

## What a system prompt controls

The system prompt is where you encode standing instructions: the tone to use,
the role to play ("you are a careful technical assistant"), formatting
requirements, topics to avoid, and any constraints on length or style.
Because it is processed first and kept in context throughout the exchange, it
exerts a strong, persistent influence on the model's behavior.

## System prompts with local models

When running a local model through Ollama, you can set the system prompt in a
Modelfile with the `SYSTEM` instruction, or pass it per request through the
API. A well-written system prompt is one of the cheapest and most effective
ways to steer a local model, since it changes the behavior of every response
without any fine-tuning.

## Good practice

Keep system-prompt instructions clear, specific, and positive ("respond in
concise prose") rather than vague. Conflicting or overly long instructions
dilute their effect, so the most reliable system prompts are short and
unambiguous about the behavior they expect.
