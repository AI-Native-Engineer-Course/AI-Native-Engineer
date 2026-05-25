"""
capstone_weather_assistant.py

Module 5 Capstone Application: a Weather Assistant that ties together
every concept from the module —
    - A custom trained deep-learning model (Lecture 2)
    - A decision/inference layer that turns predictions into advice (Lecture 3)
    - Pretrained Hugging Face models that let the user ask questions
      in natural English (Lecture 4)

User flow:
    User types:  "Should I water the lawn tomorrow?"
    Assistant:   classifies intent (zero-shot) → runs the weather model
                 → applies decision rules → returns a friendly answer.

Prerequisites — run in this order before launching the assistant:
    1. python generate_weather_data.py        # creates orlando_weather.csv
    2. python lecture2_train_weather_model.py # creates weather_model.keras + scaler
    3. pip install transformers torch          # for the HF pipeline
    4. python capstone_weather_assistant.py

This is intentionally a single file so the class can read it top-to-bottom
during the live demo.
"""

import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"   # silences the oneDNN message
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"     # silences absl/C++ info+warning logs

import json
import pickle
import numpy as np
import tensorflow as tf
tf.get_logger().setLevel("ERROR")
from transformers import pipeline

# ===========================================================================
# Component 1 — load the custom trained model
# ===========================================================================
print("Loading custom weather model ...")
weather_model = tf.keras.models.load_model("weather_model.keras")
with open("weather_scaler.pkl", "rb") as f:
    scaler = pickle.load(f)
with open("feature_columns.json") as f:
    feature_cols = json.load(f)


def predict_tomorrow_temp(today: dict) -> float:
    doy = today["day_of_year"]
    row = {
        "temp_max_f":        today["temp_max_f"],
        "temp_min_f":        today["temp_min_f"],
        "temp_mean_f":       today["temp_mean_f"],
        "precip_in":         today["precip_in"],
        "wind_max_mph":      today["wind_max_mph"],
        "humidity_mean":     today["humidity_mean"],
        "pressure_mean_hpa": today["pressure_mean_hpa"],
        "doy_sin":           float(np.sin(2 * np.pi * doy / 365.25)),
        "doy_cos":           float(np.cos(2 * np.pi * doy / 365.25)),
    }
    X = np.array([[row[c] for c in feature_cols]], dtype="float32")
    return float(weather_model.predict(scaler.transform(X), verbose=0).flatten()[0])


# ===========================================================================
# Component 2 — load Hugging Face NLP for intent classification
# ===========================================================================
print("Loading Hugging Face intent classifier ...")
intent_classifier = pipeline(
    "zero-shot-classification", model="facebook/bart-large-mnli", framework="pt"
)

INTENTS = {
    "outdoor activity recommendation": "activity",
    "lawn watering decision":          "watering",
    "heat or temperature warning":     "heat",
    "general weather forecast":        "forecast",
}


def classify_intent(user_question: str) -> str:
    """Map free-form English to one of the four supported intents."""
    result = intent_classifier(user_question, candidate_labels=list(INTENTS.keys()))
    top_label = result["labels"][0]
    return INTENTS[top_label]


# ===========================================================================
# Component 3 — decision layer
# ===========================================================================
def answer_question(today: dict, user_question: str) -> str:
    intent = classify_intent(user_question)
    tomorrow_temp = predict_tomorrow_temp(today)
    wet_today = today["precip_in"] >= 0.10

    if intent == "watering":
        if tomorrow_temp >= 85 and not wet_today:
            return (
                f"Yes — tomorrow's predicted high mean temp is {tomorrow_temp:.1f}°F "
                f"and today was dry. Water this evening before 8 PM."
            )
        if wet_today:
            return "No need — there's enough rain today to skip watering."
        return f"Probably not needed — tomorrow is mild ({tomorrow_temp:.1f}°F)."

    if intent == "activity":
        if tomorrow_temp >= 88 and today["humidity_mean"] >= 75:
            return (
                f"Tomorrow looks hot and humid ({tomorrow_temp:.1f}°F). "
                f"Plan any outdoor activity before 9 AM."
            )
        if 70 <= tomorrow_temp <= 85:
            return (
                f"Perfect outdoor weather tomorrow — predicted {tomorrow_temp:.1f}°F. "
                f"Any time of day works."
            )
        return (
            f"Tomorrow will feel like {tomorrow_temp:.1f}°F. "
            f"Aim for the warmest part of the day if you're going outside."
        )

    if intent == "heat":
        if tomorrow_temp >= 95:
            return (
                f"EXTREME heat warning: tomorrow's predicted mean is {tomorrow_temp:.1f}°F. "
                f"Limit outdoor exposure and hydrate aggressively."
            )
        if tomorrow_temp >= 88:
            return (
                f"High heat tomorrow ({tomorrow_temp:.1f}°F). "
                f"Take a 5-minute break every 30 minutes if working outside."
            )
        return f"No heat warning — tomorrow predicted around {tomorrow_temp:.1f}°F."

    # default = general forecast
    return (
        f"My deep learning model predicts tomorrow's mean temperature in Orlando "
        f"will be about {tomorrow_temp:.1f}°F."
    )


# ===========================================================================
# Component 4 — interactive demo
# ===========================================================================
TODAY = dict(
    temp_max_f=91, temp_min_f=74, temp_mean_f=82,
    precip_in=0.0, wind_max_mph=9, humidity_mean=78,
    pressure_mean_hpa=1014, day_of_year=200,
)

print("\n" + "=" * 60)
print("WEATHER ASSISTANT — ask anything about tomorrow's weather")
print("Today's snapshot:")
for k, v in TODAY.items():
    print(f"   {k:18s} = {v}")
print("Type 'quit' to exit.")
print("=" * 60 + "\n")

DEMO_QUESTIONS = [
    "Should I water the lawn tomorrow?",
    "Is it safe for my kids to play soccer outside in the afternoon?",
    "Will it be dangerously hot tomorrow?",
    "What's the weather going to be like tomorrow?",
]

print("Running scripted demo questions first ...\n")
for q in DEMO_QUESTIONS:
    print(f"YOU: {q}")
    print(f"ASSISTANT: {answer_question(TODAY, q)}\n")

# Optional interactive REPL — uncomment if you have time live
# while True:
#     q = input("YOU: ").strip()
#     if q.lower() in {"quit", "exit", "q"}:
#         break
#     print(f"ASSISTANT: {answer_question(TODAY, q)}\n")
