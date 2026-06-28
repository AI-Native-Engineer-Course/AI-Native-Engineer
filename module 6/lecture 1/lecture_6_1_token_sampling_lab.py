"""
lecture_6_1_token_sampling_lab.py
---------------------------------
Companion script for Module 6, Lecture 6.1 hands-on exercise.

Demonstrates two foundational concepts from the lecture:
  1. Tokenization — how text turns into tokens (the unit LLMs see).
  2. Sampling controls — how temperature changes model output.

Prerequisites:
  - Ollama installed and running (https://ollama.com)
  - llama3.2:3b pulled:  ollama pull llama3.2
  - Python 3.10+
  - pip install ollama tiktoken

If Ollama is not yet installed, the tokenization section still works on its own
because tiktoken uses an OpenAI tokenizer that ships with the package. The Ollama
calls in PART B will be skipped if the server is unreachable.
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# PART A — Tokenization
# ---------------------------------------------------------------------------
# Tokenizers differ between model families, but they all behave similarly.
# We use cl100k_base (the GPT-4 tokenizer) because it's freely available and
# its token boundaries look almost identical to what Llama 3's tokenizer
# produces for English text.

def show_tokens(text: str) -> None:
    """Print the tokens produced by cl100k_base for a string."""
    try:
        import tiktoken
    except ImportError:
        print("tiktoken not installed. Run: pip install tiktoken")
        return

    enc = tiktoken.get_encoding("cl100k_base")
    token_ids = enc.encode(text)
    token_strings = [enc.decode([tid]) for tid in token_ids]

    print(f"\nINPUT  : {text!r}")
    print(f"TOKENS : {token_strings}")
    print(f"COUNT  : {len(token_ids)} tokens for {len(text)} characters")
    print(f"RATIO  : {len(text) / len(token_ids):.2f} chars/token")


def part_a_tokenization() -> None:
    print("=" * 70)
    print("PART A — Tokenization")
    print("=" * 70)
    print("Watch how different kinds of text produce different token counts.")

    samples = [
        # Plain English — predictable, around 3-4 chars/token
        "The quick brown fox jumps over the lazy dog.",
        # Long made-up word — splits into many tokens
        "antidisestablishmentarianism",
        # Code — tokenizes very differently than prose
        "def fibonacci(n): return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)",
        # Non-English — typically more tokens per character
        "今日はいい天気ですね。",
        # Numbers — surprising tokenization patterns
        "The total was $1,234,567.89 on 2026-05-11.",
    ]

    for s in samples:
        show_tokens(s)

    print("\nObservation:")
    print("  Rule of thumb: 1 token ~= 0.75 English words. But code, numbers,")
    print("  and non-English text break that ratio. Always measure for your")
    print("  actual data when planning context-window budgets.\n")


# ---------------------------------------------------------------------------
# PART B — Sampling: Temperature
# ---------------------------------------------------------------------------
# Same prompt, same model, three temperatures. The variance in outputs is the
# entire point. Temperature 0.0 should produce nearly identical responses on
# repeated calls. Temperature 1.0+ should produce visibly different responses.

def call_ollama(prompt: str, temperature: float, seed: int | None = None) -> str:
    """Send a single completion request to local Ollama."""
    try:
        import ollama
    except ImportError:
        return "[ollama package not installed: pip install ollama]"

    options = {"temperature": temperature}
    if seed is not None:
        options["seed"] = seed

    try:
        response = ollama.generate(
            model="llama3.2",
            prompt=prompt,
            options=options,
        )
        return response["response"].strip()
    except Exception as e:
        return f"[Ollama error: {e}. Is the server running? Try: ollama serve]"


def part_b_sampling() -> None:
    print("=" * 70)
    print("PART B — Temperature and Sampling")
    print("=" * 70)
    print("One prompt. Three temperatures. Two runs each. Watch the variance.")

    prompt = (
        "In one sentence, describe a sunrise to someone who has never seen one."
    )

    for temp in (0.0, 0.7, 1.3):
        print(f"\n--- Temperature {temp} ---")
        for run in (1, 2):
            response = call_ollama(prompt, temperature=temp)
            print(f"  Run {run}: {response}")

    print("\nObservation:")
    print("  At temperature 0.0 the two runs should be nearly identical")
    print("  (deterministic next-token selection). At 1.3 the runs should")
    print("  diverge clearly. This is the randomness knob in action.\n")


# ---------------------------------------------------------------------------
# PART C — Reproducibility with a fixed seed
# ---------------------------------------------------------------------------

def part_c_seed() -> None:
    print("=" * 70)
    print("PART C — Reproducibility via seed")
    print("=" * 70)
    print("Same prompt, same seed, temperature 0.7. Both runs should match.")

    prompt = "Give me three creative names for a robot vacuum cleaner."

    for run in (1, 2):
        response = call_ollama(prompt, temperature=0.7, seed=42)
        print(f"\n  Run {run} (seed=42): {response}")

    print("\nObservation:")
    print("  A fixed seed makes sampling deterministic even at non-zero")
    print("  temperature. This is what makes LLM behavior testable.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    #part_a_tokenization()

    #if "--tokens-only" in sys.argv:
    #    sys.exit(0)

    #part_b_sampling()
    part_c_seed()

    print("Done. Open the script in your editor and try changing the prompts.")
