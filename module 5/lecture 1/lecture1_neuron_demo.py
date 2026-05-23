"""
lecture1_neuron_demo.py

Lecture 1 hands-on: build a single artificial neuron and a tiny network
from scratch with NumPy — no Keras, no PyTorch — so students can SEE
exactly what a deep learning model is doing.

We demonstrate three things in order:
    1. A single neuron computing weighted sum + activation.
    2. Why a single neuron CANNOT learn XOR (linear separability).
    3. A 2-layer network that CAN learn XOR.

This is the entire essence of deep learning compressed to ~80 lines.

    pip install numpy
    python lecture1_neuron_demo.py
"""

import numpy as np

np.random.seed(7)

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))

def sigmoid_deriv(a):
    # derivative expressed in terms of the activation value a = sigmoid(z)
    return a * (1.0 - a)

# ---------------------------------------------------------------------------
# Part 1 — a single neuron
# ---------------------------------------------------------------------------
print("=" * 60)
print("Part 1: One neuron, computed by hand")
print("=" * 60)

inputs = np.array([0.5, -0.2, 0.1])     # three input features
weights = np.array([0.4, -0.6, 0.2])    # one weight per feature
bias = 0.1

z = np.dot(inputs, weights) + bias
a = sigmoid(z)
print(f"Inputs:   {inputs}")
print(f"Weights:  {weights}")
print(f"Bias:     {bias}")
print(f"Weighted sum z = {z:.4f}")
print(f"Activation a = sigmoid(z) = {a:.4f}")
print()
print("That's the entire forward pass of one neuron. Everything else in")
print("deep learning is stacking, repeating, and tuning this one operation.")

# ---------------------------------------------------------------------------
# Part 2 — XOR cannot be solved by a single neuron
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("Part 2: A single neuron CANNOT learn XOR")
print("=" * 60)

X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
y = np.array([[0], [1], [1], [0]], dtype=float)  # XOR truth table

# Single-neuron model: w (2,) and b
w = np.random.randn(2, 1) * 0.5
b = 0.0
lr = 0.5

for epoch in range(2000):
    a = sigmoid(X @ w + b)
    error = a - y
    grad_w = X.T @ (error * sigmoid_deriv(a)) / len(X)
    grad_b = np.mean(error * sigmoid_deriv(a))
    w -= lr * grad_w
    b -= lr * grad_b

print("Predictions after 2000 epochs of single-neuron training:")
preds = sigmoid(X @ w + b).flatten()
for xi, yi, pi in zip(X, y.flatten(), preds):
    print(f"  input={xi}  target={int(yi)}  predicted={pi:.3f}")
print("Notice: the network can't get below ~0.5 for one class. XOR is not")
print("linearly separable, so no single line (= one neuron) can split it.")

# ---------------------------------------------------------------------------
# Part 3 — a 2-layer network CAN learn XOR
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("Part 3: A 2-layer network learns XOR")
print("=" * 60)

# Layer sizes: 2 -> 4 -> 1
W1 = np.random.randn(2, 4) * 0.5
b1 = np.zeros((1, 4))
W2 = np.random.randn(4, 1) * 0.5
b2 = np.zeros((1, 1))

for epoch in range(5000):
    # forward
    a1 = sigmoid(X @ W1 + b1)
    a2 = sigmoid(a1 @ W2 + b2)

    # backward (mean squared error)
    d2 = (a2 - y) * sigmoid_deriv(a2)
    d1 = (d2 @ W2.T) * sigmoid_deriv(a1)

    W2 -= lr * (a1.T @ d2) / len(X)
    b2 -= lr * np.mean(d2, axis=0, keepdims=True)
    W1 -= lr * (X.T @ d1) / len(X)
    b1 -= lr * np.mean(d1, axis=0, keepdims=True)

print("Predictions after 5000 epochs of 2-layer training:")
a1 = sigmoid(X @ W1 + b1)
preds = sigmoid(a1 @ W2 + b2).flatten()
for xi, yi, pi in zip(X, y.flatten(), preds):
    correct = "OK" if round(pi) == int(yi) else "WRONG"
    print(f"  input={xi}  target={int(yi)}  predicted={pi:.3f}  [{correct}]")

print()
print("Same data. Same activation function. We just added ONE hidden layer")
print("and the network learned a problem that was impossible before.")
print("That is, in 80 lines, the entire idea of deep learning.")
