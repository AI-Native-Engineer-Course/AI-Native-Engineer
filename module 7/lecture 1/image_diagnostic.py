"""
image_diagnostic.py
-------------------
Module 7 · Lecture 7.1 · Foundations of Sight
Hands-on: Your First Image Diagnostic

A reusable diagnostic tool that loads any image and prints structured information
about it: shape, dtype, per-channel min/max, dominant channel, and HSV summary.
Saves per-channel grayscale outputs so you can SEE what the camera captured.

Usage:
    python image_diagnostic.py path/to/image.jpg
    python image_diagnostic.py path/to/image.jpg --outdir ./out

If no path is given, the script downloads a sample image and runs on it so you
can verify the install is working.
"""

import sys
import os
import argparse
from pathlib import Path

import cv2
import numpy as np


SAMPLE_URL = "https://ultralytics.com/images/bus.jpg"


def ensure_sample(local_path: str = "bus.jpg") -> str:
    """If the sample image is not present, download it once."""
    if os.path.exists(local_path):
        return local_path
    try:
        from urllib.request import urlretrieve
        print(f"Downloading sample image -> {local_path}")
        urlretrieve(SAMPLE_URL, local_path)
        return local_path
    except Exception as exc:
        raise SystemExit(f"Could not fetch sample image: {exc}")


def diagnose(image_path: str, outdir: str) -> None:
    """Run the full diagnostic on a single image."""
    # ------- Step 1: load and validate
    img = cv2.imread(image_path)
    if img is None:
        raise SystemExit(
            f"cv2.imread returned None. Check the path: {image_path}\n"
            "Reminder: OpenCV does NOT raise on bad paths — it silently returns None."
        )

    print("=" * 60)
    print(f"IMAGE: {image_path}")
    print("=" * 60)

    # ------- Step 2: report shape, dtype, byte size
    h, w = img.shape[:2]
    channels = img.shape[2] if img.ndim == 3 else 1
    print(f"Shape           : {img.shape}    (height, width, channels)")
    print(f"Dtype           : {img.dtype}")
    print(f"Total pixels    : {h * w:,}")
    print(f"Memory footprint: {img.nbytes / 1024:.1f} KB")

    # ------- Step 3: per-channel statistics (REMEMBER: OpenCV order is B, G, R)
    if channels == 3:
        b, g, r = cv2.split(img)
        channel_stats = [
            ("Blue ", b),
            ("Green", g),
            ("Red  ", r),
        ]
        print("\nPer-channel statistics (OpenCV order is BGR, not RGB):")
        for name, ch in channel_stats:
            print(
                f"  {name}: min={ch.min():3d}  max={ch.max():3d}  "
                f"mean={ch.mean():6.2f}  std={ch.std():6.2f}"
            )

        # which channel "dominates" in this image?
        means = {"Blue": b.mean(), "Green": g.mean(), "Red": r.mean()}
        dominant = max(means, key=means.get)
        print(f"\nDominant channel: {dominant}  (mean={means[dominant]:.2f})")

        # ------- Step 4: save each channel as a grayscale image so the user can SEE
        outdir_path = Path(outdir)
        outdir_path.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(outdir_path / "blue_channel.png"), b)
        cv2.imwrite(str(outdir_path / "green_channel.png"), g)
        cv2.imwrite(str(outdir_path / "red_channel.png"), r)
        print(f"\nSaved per-channel grayscale images to: {outdir_path.resolve()}")

        # ------- Step 5: HSV summary (the right space for color thresholding)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = cv2.split(hsv)
        print("\nHSV summary:")
        print(f"  Hue        : min={h_ch.min():3d}  max={h_ch.max():3d}  "
              f"mean={h_ch.mean():6.2f}    (OpenCV hue range: 0-179)")
        print(f"  Saturation : min={s_ch.min():3d}  max={s_ch.max():3d}  "
              f"mean={s_ch.mean():6.2f}")
        print(f"  Value      : min={v_ch.min():3d}  max={v_ch.max():3d}  "
              f"mean={v_ch.mean():6.2f}")

    else:
        print("\nThis is a single-channel image (grayscale).")
        print(f"  min={img.min()}  max={img.max()}  "
              f"mean={img.mean():.2f}  std={img.std():.2f}")

    print("\nDiagnostic complete.")
    print("Open the per-channel PNGs and compare them to the original — you will")
    print("see WHICH channel actually contains the structure you care about.")


def main():
    parser = argparse.ArgumentParser(description="OpenCV image diagnostic tool.")
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to an image file. If omitted, a sample image is downloaded.",
    )
    parser.add_argument(
        "--outdir",
        default="./diagnostic_output",
        help="Directory for per-channel grayscale outputs.",
    )
    args = parser.parse_args()

    image_path = args.path or ensure_sample()
    diagnose(image_path, args.outdir)


if __name__ == "__main__":
    main()
