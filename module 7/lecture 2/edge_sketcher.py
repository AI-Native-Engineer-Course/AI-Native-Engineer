"""
edge_sketcher.py
----------------
Module 7 · Lecture 7.2 · Mastering the OpenCV Toolbox
Hands-on: The Edge Sketcher

Turn any photograph into a pencil-sketch image using a five-step classical
OpenCV pipeline:
    1. Convert to grayscale
    2. Invert the grayscale
    3. Apply a Gaussian blur to the inverted image
    4. Invert the blurred image again
    5. Blend back with the original grayscale using a color-dodge (cv2.divide)

A Canny edge map is also produced alongside the sketch, so the room can compare
a "soft" artistic edge response (the sketch) with a "hard" binary one (Canny).

No neural network. No GPU. Runs in milliseconds on any laptop.

Usage:
    python edge_sketcher.py path/to/photo.jpg
    python edge_sketcher.py path/to/portrait.jpg --outdir ./sketch_out --kernel 21

This writes five PNGs into the output directory so you can walk through the
pipeline one stage at a time:
    1_gray.png  2_inverted.png  3_blurred.png  4_sketch.png  5_canny.png

If no path is given, a sample image is downloaded so you can verify the install.
"""

import os
import argparse
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import numpy as np


SAMPLE_URL = "https://ultralytics.com/images/zidane.jpg"


def ensure_sample(local_path: str = "zidane.jpg") -> str:
    if os.path.exists(local_path):
        return local_path
    print(f"Downloading sample image -> {local_path}")
    urlretrieve(SAMPLE_URL, local_path)
    return local_path


def pencil_sketch_stages(
    img_bgr: np.ndarray,
    kernel_size: int = 21,
    scale: float = 256.0,
    canny_lo: int = 50,
    canny_hi: int = 150,
) -> dict:
    """
    Run the pipeline and return EVERY intermediate stage, not just the result.

    This is the teaching version: it keeps each stage so you can save and
    inspect them. pencil_sketch() below is the thin "just give me the result"
    wrapper around it.

    Args:
        img_bgr: Input image in OpenCV's BGR format.
        kernel_size: Gaussian blur kernel. MUST be odd. Larger -> softer, more
                     impressionistic sketch. Smaller -> tighter, more detailed.
        scale: Divide scale. Higher -> brighter sketch. Lower -> darker.
        canny_lo: Lower Canny hysteresis threshold.
        canny_hi: Upper Canny hysteresis threshold.

    Returns:
        An ordered dict mapping stage name -> single-channel image:
            "gray", "inverted", "blurred", "sketch", "canny"
    """
    if kernel_size % 2 == 0:
        raise ValueError(
            f"Gaussian kernel must be ODD. Got {kernel_size}. "
            "This is OpenCV's most common gotcha - every filter needs a defined center pixel."
        )

    # Step 1: grayscale — edges live in intensity, not color.
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Step 2: invert — dark becomes light, light becomes dark.
    inverted = 255 - gray

    # Step 3: blur the inverted image. Kernel size controls "softness".
    blurred = cv2.GaussianBlur(inverted, (kernel_size, kernel_size), sigmaX=0)
    # blurred = cv2.medianBlur(inverted, 21)
	
    # Step 4: invert again so the blur acts as a "shadow map".
    inverted_blur = 255 - blurred

    # Step 5: color dodge — sketch = gray / inverted_blur * 256
    # cv2.divide handles uint8 saturation correctly.
    sketch = cv2.divide(gray, inverted_blur, scale=scale)

    # Bonus: a classic Canny edge map for side-by-side comparison.
    # Canny runs on the plain grayscale and returns a binary (0/255) edge image.
    canny = cv2.Canny(gray, canny_lo, canny_hi)

    return {
        "gray": gray,
        "inverted": inverted,
        "blurred": blurred,
        "sketch": sketch,
        "canny": canny,
    }


def pencil_sketch(
    img_bgr: np.ndarray, kernel_size: int = 21, scale: float = 256.0
) -> np.ndarray:
    """
    Convenience wrapper: run the pipeline and return ONLY the final
    single-channel pencil-sketch image, same H/W as the input.
    """
    return pencil_sketch_stages(img_bgr, kernel_size=kernel_size, scale=scale)["sketch"]


# Stage name -> output filename, in the order students should open them.
STAGE_FILENAMES = {
    "gray": "1_gray.png",
    "inverted": "2_inverted.png",
    "blurred": "3_blurred.png",
    "sketch": "4_sketch.png",
    "canny": "5_canny.png",
}


def main():
    parser = argparse.ArgumentParser(description="Classical OpenCV pencil sketch generator.")
    parser.add_argument("path", nargs="?", default=None,
                        help="Input image path. Downloads a sample if omitted.")
    parser.add_argument("--outdir", default="./sketch_out",
                        help="Directory for the five stage PNGs (default: ./sketch_out).")
    parser.add_argument("--kernel", type=int, default=21,
                        help="Gaussian blur kernel size — must be odd. Default 21.")
    parser.add_argument("--scale", type=float, default=256.0,
                        help="Divide scale; raises brightness of the sketch. Default 256.")
    parser.add_argument("--canny-lo", type=int, default=50,
                        help="Lower Canny hysteresis threshold. Default 50.")
    parser.add_argument("--canny-hi", type=int, default=150,
                        help="Upper Canny hysteresis threshold. Default 150.")
    args = parser.parse_args()

    image_path = args.path or ensure_sample()
    img = cv2.imread(image_path)
    if img is None:
        raise SystemExit(f"cv2.imread returned None. Check the path: {image_path}")

    print(f"Input shape : {img.shape}")
    print(f"Kernel size : {args.kernel}")
    print(f"Scale       : {args.scale}")

    stages = pencil_sketch_stages(
        img,
        kernel_size=args.kernel,
        scale=args.scale,
        canny_lo=args.canny_lo,
        canny_hi=args.canny_hi,
    )

    # Write every stage so the pipeline is visible one image at a time.
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for stage, fname in STAGE_FILENAMES.items():
        cv2.imwrite(str(outdir / fname), stages[stage])
        print(f"  wrote {fname}")

    print(f"\nSaved 5 stage images -> {outdir.resolve()}")
    print("Open them in order: 1_gray -> 2_inverted -> 3_blurred -> 4_sketch -> 5_canny.")
    print("4_sketch.png is the payoff - show it last.")
    print("\nTry it: re-run with --kernel 5 for a tight sketch, --kernel 51 for a loose one.")


if __name__ == "__main__":
    main()
