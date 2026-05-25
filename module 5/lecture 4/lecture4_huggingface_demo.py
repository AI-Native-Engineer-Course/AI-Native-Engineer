"""
lecture4_huggingface_demo.py

Lecture 4 hands-on: use four pretrained Hugging Face models inside a
single application — no training, no GPU required.

Demonstrates:
    1. Sentiment analysis      (text classification)
    2. Zero-shot classification (custom labels at inference time)
    3. Summarization
    4. Named-entity recognition

The 'pipeline' helper is Hugging Face's one-line model loader. The first
time each pipeline runs, it downloads the weights to ~/.cache/huggingface/.
Subsequent runs are offline.

    pip install transformers torch
    python lecture4_huggingface_demo.py
"""

from transformers import pipeline

REVIEW = (
    "I switched to this weather app two months ago and have been impressed. "
    "The interface is clean, severe-storm alerts arrive ten minutes earlier "
    "than the National Weather Service push notifications, and battery use "
    "is negligible. The radar still pixelates on older Android devices, but "
    "that is my only complaint."
)

ARTICLE = (
    "On August 28, 2026, Hurricane Idalia made landfall along Florida's Big "
    "Bend region as a Category 3 storm with sustained winds of 125 mph. The "
    "National Hurricane Center had upgraded the storm twice in the preceding "
    "18 hours. Governor Ron DeSantis declared a state of emergency for 49 "
    "counties. Power was restored to 80% of affected customers within 72 "
    "hours, faster than the recovery from Hurricane Ian in 2022. Damage "
    "estimates from AccuWeather totaled approximately 20 billion dollars."
)

# ---------------------------------------------------------------------------
# 1. Sentiment analysis — is the review positive or negative?
# ---------------------------------------------------------------------------
print("=" * 60)
print("1. Sentiment analysis  (distilbert-base-uncased-sst-2)")
print("=" * 60)
sentiment = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english", framework="pt"
)
result = sentiment(REVIEW)[0]
print(f"Label: {result['label']}  Score: {result['score']:.4f}")

# ---------------------------------------------------------------------------
# 2. Zero-shot — classify into labels the model has never seen before
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("2. Zero-shot classification  (facebook/bart-large-mnli)")
print("=" * 60)
zsc = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", framework="pt")
labels = ["weather", "billing complaint", "feature request", "bug report"]
result = zsc(REVIEW, candidate_labels=labels)
for label, score in zip(result["labels"], result["scores"]):
    print(f"  {label:20s}  {score:.4f}")

# ---------------------------------------------------------------------------
# 3. Summarization
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("3. Summarization  (sshleifer/distilbart-cnn-12-6)")
print("=" * 60)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", framework="pt")
result = summarizer(ARTICLE, max_length=60, min_length=20, do_sample=False)[0]
print(result["summary_text"].strip())

# ---------------------------------------------------------------------------
# 4. Named entity recognition (NER)
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("4. Named-entity recognition  (dslim/bert-base-NER)")
print("=" * 60)
ner = pipeline(
    "ner",
    model="dslim/bert-base-NER",
    aggregation_strategy="simple", framework="pt"
)
entities = ner(ARTICLE)
for ent in entities:
    print(f"  {ent['entity_group']:8s}  {ent['word']!r:35s}  score={ent['score']:.3f}")

print()
print("Four pretrained models, zero training time, ~150 lines of code.")
print("That is the value the Hugging Face Hub brings to a production app.")
