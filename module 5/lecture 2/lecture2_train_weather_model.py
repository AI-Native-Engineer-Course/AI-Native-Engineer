"""
lecture2_train_weather_model.py

Lecture 2 hands-on: train a small dense neural network to predict
tomorrow's mean temperature in Orlando, FL from today's weather features.

This is the simplest "real" deep learning workflow:
    1. Load data and engineer features
    2. Split into train / validation / test
    3. Scale features
    4. Build a small Keras dense network
    5. Train it with early stopping
    6. Evaluate on held-out data
    7. Save the trained model AND the scaler for downstream use

    pip install pandas numpy scikit-learn tensorflow
    python lecture2_train_weather_model.py

Reads: orlando_weather.csv  (run generate_weather_data.py first)
Writes:
    weather_model.keras        — the trained model
    weather_scaler.pkl         — the StandardScaler used for inputs
    feature_columns.json       — exact feature order, so inference matches
"""

import json
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks

SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

# ---------------------------------------------------------------------------
# 1. Load and engineer features
# ---------------------------------------------------------------------------
df = pd.read_csv("orlando_weather.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)

# Add day-of-year so the model can learn seasonality
df["day_of_year"] = df["date"].dt.dayofyear
df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365.25)

# TARGET: tomorrow's mean temperature
df["target_temp_mean_f"] = df["temp_mean_f"].shift(-1)
df = df.dropna(subset=["target_temp_mean_f"]).reset_index(drop=True)

feature_cols = [
    "temp_max_f", "temp_min_f", "temp_mean_f",
    "precip_in", "wind_max_mph", "humidity_mean", "pressure_mean_hpa",
    "doy_sin", "doy_cos",
]
X = df[feature_cols].values.astype("float32")
y = df["target_temp_mean_f"].values.astype("float32")

print(f"Dataset: {len(df)} samples, {len(feature_cols)} features.")

# ---------------------------------------------------------------------------
# 2. Train / val / test split (time-aware: do NOT shuffle)
# ---------------------------------------------------------------------------
# Last 10% test, previous 10% validation, the rest training. Weather is a
# time series, so we never let the model peek at "future" examples.
n = len(X)
test_start = int(n * 0.90)
val_start = int(n * 0.80)
X_train, y_train = X[:val_start], y[:val_start]
X_val,   y_val   = X[val_start:test_start], y[val_start:test_start]
X_test,  y_test  = X[test_start:], y[test_start:]
print(f"Train: {len(X_train)}  Val: {len(X_val)}  Test: {len(X_test)}")

# ---------------------------------------------------------------------------
# 3. Scale features (fit on training data ONLY)
# ---------------------------------------------------------------------------
scaler = StandardScaler().fit(X_train)
X_train_s = scaler.transform(X_train)
X_val_s   = scaler.transform(X_val)
X_test_s  = scaler.transform(X_test)

# ---------------------------------------------------------------------------
# 4. Build a small dense network
# ---------------------------------------------------------------------------
model = models.Sequential([
    layers.Input(shape=(len(feature_cols),)),
    layers.Dense(64, activation="relu"),
    layers.Dropout(0.15),
    layers.Dense(32, activation="relu"),
    layers.Dense(1),   # regression → one linear output
])
model.compile(optimizer="adam", loss="mse", metrics=["mae"])
model.summary()

# ---------------------------------------------------------------------------
# 5. Train with early stopping
# ---------------------------------------------------------------------------
early_stop = callbacks.EarlyStopping(
    monitor="val_loss", patience=15, restore_best_weights=True
)
history = model.fit(
    X_train_s, y_train,
    validation_data=(X_val_s, y_val),
    epochs=200, batch_size=32, verbose=2,
    callbacks=[early_stop],
)

