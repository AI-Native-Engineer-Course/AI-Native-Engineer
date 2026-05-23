"""
lecture3_weather_advisor.py

Lecture 3 hands-on: take the trained model from Lecture 2 and turn it
into something that makes ACTUAL DECISIONS — recommending outdoor
activities, alerting on heat risk, deciding watering schedules.

This shows the full inference pipeline:
    1. Load the saved model, scaler, and feature schema
    2. Accept new input (today's conditions)
    3. Run inference
    4. Apply business rules / decision logic on top of the prediction
    5. Return human-readable output

Run after Lecture 2 has produced the saved model:
    pip install pandas numpy scikit-learn tensorflow
    python lecture3_weather_advisor.py
"""

import json
import pickle
import numpy as np
import tensorflow as tf

# ---------------------------------------------------------------------------
# 1. Load the trained artifacts
# ---------------------------------------------------------------------------
print("Loading model and preprocessing artifacts ...")
model = tf.keras.models.load_model("weather_model.keras")
with open("weather_scaler.pkl", "rb") as f:
    scaler = pickle.load(f)
with open("feature_columns.json") as f:
    feature_cols = json.load(f)
print(f"Model expects {len(feature_cols)} features in this order:")
print("  ", feature_cols)


# ---------------------------------------------------------------------------
# 2. Inference helper — encapsulate the entire prediction pipeline
# ---------------------------------------------------------------------------
def predict_tomorrow_temp(today: dict) -> float:
    """Return predicted mean temp (°F) for tomorrow given today's reading.

    Args:
        today: dict with keys for each raw measurement, plus 'day_of_year'.

    Returns:
        Predicted mean temperature in °F as a Python float.
    """
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
    X_scaled = scaler.transform(X)
    pred = float(model.predict(X_scaled, verbose=0).flatten()[0])
    return pred


# ---------------------------------------------------------------------------
# 3. Decision layer — turn a number into advice
# ---------------------------------------------------------------------------
def advise(today: dict) -> dict:
    """Combine a model prediction with rule-based logic to produce advice."""
    tomorrow_temp = predict_tomorrow_temp(today)

    # Heat-risk classification (Florida-appropriate thresholds)
    if tomorrow_temp >= 95:
        heat = "EXTREME — limit outdoor time, hydrate aggressively."
    elif tomorrow_temp >= 88:
        heat = "HIGH — outdoor work fine with breaks every 30 min."
    elif tomorrow_temp >= 75:
        heat = "MODERATE — pleasant outdoor day."
    elif tomorrow_temp >= 60:
        heat = "MILD — light jacket in the morning."
    else:
        heat = "COOL — uncommon for Orlando; layer up."

    # Watering decision: only water if hot AND dry today AND likely dry tomorrow
    likely_rain_today = today["precip_in"] >= 0.10
    if tomorrow_temp >= 85 and not likely_rain_today:
        watering = "Water the lawn this evening."
    elif likely_rain_today:
        watering = "Skip watering — already wet."
    else:
        watering = "No watering needed."

    # Activity recommendation
    if tomorrow_temp >= 88 and today["humidity_mean"] >= 75:
        activity = "Best outdoor activity: early-morning walk before 9 AM."
    elif 70 <= tomorrow_temp <= 85:
        activity = "Best outdoor activity: any time of day — ideal conditions."
    elif tomorrow_temp < 60:
        activity = "Best outdoor activity: afternoon, when warmest."
    else:
        activity = "Best outdoor activity: morning or evening hours."

    # Confidence flag — model is less reliable when today is unusual
    extreme_today = today["temp_max_f"] >= 100 or today["temp_min_f"] <= 35
    if extreme_today:
        confidence = "low (today is an outlier vs training data)"
    else:
        confidence = "normal"

    return {
        "predicted_tomorrow_temp_f": round(tomorrow_temp, 1),
        "heat_advisory": heat,
        "watering_decision": watering,
        "activity_recommendation": activity,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# 4. Demo with a few example "todays"
# ---------------------------------------------------------------------------
scenarios = [
    {
        "label": "Typical July day",
        "today": dict(temp_max_f=91, temp_min_f=74, temp_mean_f=82,
                      precip_in=0.0, wind_max_mph=9, humidity_mean=78,
                      pressure_mean_hpa=1014, day_of_year=200),
    },
    {
        "label": "Cool January morning",
        "today": dict(temp_max_f=62, temp_min_f=44, temp_mean_f=53,
                      precip_in=0.0, wind_max_mph=11, humidity_mean=58,
                      pressure_mean_hpa=1020, day_of_year=18),
    },
    {
        "label": "Wet afternoon, late August",
        "today": dict(temp_max_f=87, temp_min_f=73, temp_mean_f=80,
                      precip_in=0.85, wind_max_mph=16, humidity_mean=92,
                      pressure_mean_hpa=1009, day_of_year=240),
    },
]

print()
for s in scenarios:
    print("=" * 60)
    print(s["label"])
    print("=" * 60)
    result = advise(s["today"])
    for k, v in result.items():
        print(f"  {k:30s}: {v}")
    print()
