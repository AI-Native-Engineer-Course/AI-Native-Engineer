"""
lecture_6_2_ollama_tour.py
--------------------------
Companion script for Module 6, Lecture 6.2 hands-on exercise.

Demonstrates the two Python paths to talking to local Ollama:
  PART A — the official `ollama` Python package
  PART B — the standard `openai` SDK pointed at Ollama's OpenAI-compatible URL
  PART C — multi-turn chat with a system prompt and conversation history
  PART D — streaming responses (token-by-token output)

Prerequisites:
  - Ollama installed and running (https://ollama.com)
  - llama3.2 pulled:  ollama pull llama3.2
  - Python 3.10+
  - pip install ollama openai

The PART B section sets api_key="ollama" — Ollama does not check the key, but
the OpenAI SDK requires a non-empty string. That's the only quirk to remember
when adapting any OpenAI-based code to Ollama.
"""

from __future__ import annotations

MODEL = "llama3.2"
OLLAMA_BASE_URL = "http://localhost:11434/v1"


# ---------------------------------------------------------------------------
# PART A — Official Ollama Python package
# ---------------------------------------------------------------------------

def part_a_native_sdk() -> None:
    print("=" * 70)
    print("PART A — The official `ollama` Python package")
    print("=" * 70)

    import ollama

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "In one sentence: what is the capital of Japan?",
            }
        ],
        options={"temperature": 0.1},
    )

    print(f"\nModel:    {response['model']}")
    print(f"Response: {response['message']['content']}")
    print(f"Tokens:   prompt={response.get('prompt_eval_count', 'n/a')}, "
          f"response={response.get('eval_count', 'n/a')}")


# ---------------------------------------------------------------------------
# PART B — OpenAI SDK pointed at Ollama
# ---------------------------------------------------------------------------

def part_b_openai_sdk() -> None:
    print("\n" + "=" * 70)
    print("PART B — OpenAI SDK pointed at Ollama")
    print("=" * 70)
    print("Identical prompt, identical model. Only the base URL changes.")

    from openai import OpenAI

    client = OpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="ollama",  # required by the SDK, ignored by Ollama
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "In one sentence: what is the capital of Japan?",
            }
        ],
        temperature=0.1,
    )

    print(f"\nModel:    {response.model}")
    print(f"Response: {response.choices[0].message.content}")
    print("\nThis is the entire portability story. Any code that already")
    print("uses the OpenAI SDK works against Ollama with one config change.")


# ---------------------------------------------------------------------------
# PART C — Multi-turn chat with a system prompt
# ---------------------------------------------------------------------------

def part_c_multi_turn() -> None:
    print("\n" + "=" * 70)
    print("PART C — Multi-turn chat with a system prompt")
    print("=" * 70)
    print("System prompts shape the model's behavior for the whole session.")

    import ollama

    messages = [
        {
            "role": "system",
            "content": (
                "You are a Python expert. Always respond with a code block "
                "first, then a one-sentence explanation. Never apologize."
            ),
        },
        {
            "role": "user",
            "content": "How do I reverse a list?",
        },
    ]

    # First turn
    response = ollama.chat(model=MODEL, messages=messages,
                           options={"temperature": 0.2})
    assistant_reply_1 = response["message"]["content"]
    print(f"\n[Turn 1 — assistant]\n{assistant_reply_1}")

    # Append the assistant's reply to history, then ask a follow-up
    messages.append({"role": "assistant", "content": assistant_reply_1})
    messages.append({
        "role": "user",
        "content": "Now do the same thing without modifying the original list.",
    })

    response = ollama.chat(model=MODEL, messages=messages,
                           options={"temperature": 0.2})
    print(f"\n[Turn 2 — assistant]\n{response['message']['content']}")


# ---------------------------------------------------------------------------
# PART D — Streaming responses
# ---------------------------------------------------------------------------

def part_d_streaming() -> None:
    print("\n" + "=" * 70)
    print("PART D — Streaming responses (tokens as they're generated)")
    print("=" * 70)

    import ollama

    stream = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "Count from 1 to 5, with a brief reason why each "
                           "number is interesting. Be concise.",
            }
        ],
        stream=True,
        options={"temperature": 0.5, "num_predict": 200},
    )

    print()
    for chunk in stream:
        print(chunk["message"]["content"], end="", flush=True)
    print("\n\nStreaming is what makes chat UIs feel responsive — you don't")
    print("wait for the full response, you watch it materialize.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        part_a_native_sdk()
        part_b_openai_sdk()
        part_c_multi_turn()
        part_d_streaming()
    except Exception as e:
        print(f"\n[Error] {type(e).__name__}: {e}")
        print("Is Ollama running and have you pulled llama3.2?")
        print("  ollama serve   # in another terminal (usually auto-started)")
        print("  ollama pull llama3.2")
